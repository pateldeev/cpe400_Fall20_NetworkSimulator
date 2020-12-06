from collections import defaultdict

import Constants as C
import Helper as H
import PacketTypes as PT


# A NetworkNode (router) consists of
#   - name: name string
#   - xy: location pair
#   - links: set of links to neighboring nodes (name of nodes).
#   - battery: battery level between 0.0 (dead) and 1.0 (full).
#   - lat: last-alive-time. Represents the simulation time when node is estimated to go offline.
#   - rmt: routing multi-table for possible routes. See associated paper for structure.
#          the rmt is represented by a dictionary mapping each destination node to all its rmt entries
#   - p_hat: estimated number of packets to be sent by node over the next time-step.
#   - p_sample: total number of packets sent over the last time-step.
class NetworkNode:
	# Create Node
	def __init__(self, name, xy, battery):
		assert 0.0 <= battery <= 1.0

		self.name = name
		self.xy = xy
		self.links = set()
		self.battery = battery
		self.lat = 0
		self.rmt = defaultdict(list)
		self.p_hat = 0
		self.p_sample = 0

		# Keeps track of route discovery messages in flight.
		# Used to determine if node has already send route discovery messages for nodes.
		# Maps destination name to time step when rd messages were sent.
		self.rd_in_flight = {}

		# Keeps track of route update messages in flight.
		# Used to determine if node has recently sent route update messages for a specific route.
		# Maps route name to time step when update messages was sent.
		self.ru_in_flight = defaultdict(int)

		# Keeps track of recently responded rd messages.
		# This is to prevent repeated responses to the same route discovery message.
		# Maps route name to latest response time.
		self.rd_responded = defaultdict(dict)

		# Keep track of number of RP packets sent and received from each destination node.
		# Also keep track of where the packets came from by mapping route name to list of (time, next/previous hop).
		self.num_rp_sent = defaultdict(int)
		self.rp_sent = defaultdict(list)
		self.num_rp_received = defaultdict(int)
		self.rp_received = defaultdict(list)

	def is_alive(self):
		return self.battery > 0.0

	# Progress to next time step. This will update the rolling history of samples and recompute the lat if requested.
	def progress(self, ts, update_estimates):
		if not self.is_alive():
			# Node is dead.
			self.battery = 0.0
			return

		# Update battery level based on actual number of packets sent over last timestamp.
		self.battery -= (C.ECR_d_c + self.p_sample * C.ECR_d_p)

		if update_estimates:
			# Apply (Eq. 2) from report to compute estimated number of packets to be send over the next second.
			self.p_hat = C.ECR_alpha * self.p_hat + (1 - C.ECR_alpha) * self.p_sample

			# Apply (Eq. 1) from report to compute estimate of when node will be depleted.
			self.lat = ts + (self.battery / (C.ECR_d_c + self.p_hat * C.ECR_d_p))

		# Update rmt entries according to (Eq. 4).
		for _, entries in self.rmt.items():
			for i, (next_hop, lat_r, d_f) in enumerate(entries):
				if self.lat < lat_r:
					entries[i] = (next_hop, self.lat, 0)

		# Set number of samples to zero for next iteration.
		self.p_sample = 0

	# Sorts rmt so route to a given destination are sorted.
	def sort_rmt(self):
		# Sort according to criteria defined by ECR paper. Pick optimally know route.
		for dst, entries in self.rmt.items():
			if len(entries) > 1:
				try:
					entries.sort(key=lambda e, rmt=self.rmt: (e[1], max([0] + [next_hop_entry[1] for next_hop_entry in rmt[e[0]]])), reverse=True)
				except:
					print(self.rmt)
					exit()

	# Update or create rmt entry for specific destination and next_hop pair. See associated paper for details.
	# Returns: (lat_r, discount factor)
	def update_or_create_rmt_entry(self, dst, next_hop, lat_r, df, ts):
		# Find rmt entry.
		i = next((i for i, (entry_next_hop, _, _) in enumerate(self.rmt[dst]) if entry_next_hop == next_hop), None)

		# Use (Eq. 3) to compute value for rmt table.
		lat_r = min(self.lat, ts + max(0, C.ECR_gamma * (lat_r - ts)))
		df = 0 if lat_r == self.lat else (df + 1)

		if i is None:
			# Create new rmt entry.
			self.rmt[dst].append((next_hop, lat_r, df))
		else:
			# Update existing rmt entry.
			self.rmt[dst][i] = (next_hop, lat_r, df)

		return lat_r, df

	# Returns the known route to destination by searching through the rmt.
	# Returns (next_hop, expected_lat_r, expected discount factor)
	# Returns (None, None, None) if no route is found.
	def get_best_route(self, dst):
		self.sort_rmt()
		return self.rmt[dst][0] if self.rmt[dst] else (None, None, None)

	# Remove routes to dead neighbors.
	def cleanup_dead_neighbor(self, neighbor_name):
		for k in self.rmt:
			self.rmt[k] = [e for e in self.rmt[k] if e[0] != neighbor_name]

	# Helper function to generate route discover packets (one for each neighbor) to find a route to the destination
	# Returns pair: (list of discover packets, boolean if there was timeout error).
	# Note that, if route discover packets have already been sent out recently, the returned list will be empty.
	# neighbors_filter can be used specify if the discover messages should only be send to certain neighbors.
	def generate_route_discover_packets(self, dst, ts, neighbors_filter=None):
		rd_pkts = []
		timeout_error = False

		if dst in self.rd_in_flight and neighbors_filter is None:
			# We have send discover messages already.
			if self.rd_in_flight[dst] + C.ECR_RD_Timeout <= ts:
				# No route found! Discover messages timed out!
				timeout_error = True
		elif dst not in self.rd_in_flight or neighbors_filter is not None:
			# Generate RD packets to each neighbor.
			neighbors_sent = set()
			for _, entries in self.rmt.items():
				for next_hop, _, _ in entries:
					if next_hop not in neighbors_sent and (not neighbors_filter or next_hop in neighbors_filter):
						discovery_msg = PT.ERC_RD(src=self.name, dst_desired=dst, route=[self.name])
						pkt = PT.Packet(current_node=self.name, next_hop=next_hop, msg=discovery_msg, sent_ts=ts)
						rd_pkts.append(pkt)
						neighbors_sent.add(next_hop)
			if neighbors_filter is None:
				self.rd_in_flight[dst] = ts

		return rd_pkts, timeout_error

	# Tries to send packet to destination.
	# Returns a tuple: (list of new in-flight packets, boolean if packet was sent, boolean if there was an error).
	# If the destination is the node's rmt, the packet will be sent. If it is not, the node will send RD messages.
	def attempt_to_send_packet(self, dst, ts, log, msg_num=None):
		pkts = []
		msg_sent = error = False
		rt_name = H.get_route_name(src=self.name, dst=dst)

		# Get best known route. Could be None if unknown.
		next_hop, expected_lat_r, expected_df = self.get_best_route(dst)

		if not self.is_alive():
			log.write('  Node [{}] is dead. It cannot send packets required by packets file!'.format(self.name), is_packet=True, is_error=True)
			error = True
		elif next_hop:
			# Route is known. Send packet.
			if not msg_num:
				self.num_rp_sent[dst] += 1
				msg_num = self.num_rp_sent[dst]
			rp_msg = PT.ERC_RP(src=self.name, dst=dst, expected_discount_factor=expected_df, expected_lat_r=expected_lat_r, payload=msg_num)
			pkts.append(PT.Packet(current_node=self.name, next_hop=next_hop, msg=rp_msg, sent_ts=ts))
			msg_sent = True
			log.write("  Node [{}] sending pkt [{}] to destination [{}] through known route with next hop [{}].".format(self.name, rp_msg.payload, dst, next_hop), is_packet=True)
			self.rp_sent[rt_name].append((ts, next_hop))

			# If enough packets have been sent along route, selectively resend RD messages to get updated information along other known routes.
			if rp_msg.payload % C.ECR_RD_Resend == 0:
				new_pkts_rd, _ = self.generate_route_discover_packets(dst=dst, ts=ts, neighbors_filter={nh for nh, _, _ in self.rmt[dst] if nh != next_hop})
				if new_pkts_rd:
					pkts.extend(new_pkts_rd)
					for new_pkt in new_pkts_rd:
						log.write("  Node [{}] selectively sending out RD message to [{}] to get updated information on route to [{}]".format(self.name, new_pkt.next_hop, dst))

		else:
			# Route is not known. Generate route discover packet if necessary.
			pkts, timeout_error = self.generate_route_discover_packets(dst, ts)
			if timeout_error:
				# No route found! Discover messages timed out!
				log.write("  Node [{}] could not find route to [{}]. The sent RD messages have timed out!".format(self.name, dst), is_error=True)
				error = True
			elif not pkts:
				# Wait for send discover messages to return route.
				log.write("  Node [{}] is still waiting to get back RR messages for route to [{}].".format(self.name, dst))
			else:
				log.write("  Node [{}] does not have route to [{}]. Sending out [{}] RD messages to neighbors.".format(self.name, dst, len(pkts)))

		return pkts, msg_sent, error

	# Handle message and return pair of (list any new in-flight messages that result, if an error occurred)
	def handle_packet(self, packet, ts, log):
		assert packet.next_hop == self.name and packet.sent_ts < ts, "In flight packet is ill-formed!"
		new_pkts = []
		had_err = False
		if not self.is_alive():
			return new_pkts, had_err
		msg = packet.msg

		if packet.type == 'RD':
			rt_name = H.get_route_name(src=msg.src, dst=msg.dst)

			# Handle route discovery message.
			if self.name == msg.dst:
				# This is the destination node. Return route response.
				response_msg = PT.ERC_RR(route_src=msg.src, route_dst=self.name, discount_factor=0, lat_r=self.lat, route=msg.rt)
				response_packet = PT.Packet(current_node=self.name, next_hop=msg.rt[-1], msg=response_msg, sent_ts=ts)

				new_pkts.append(response_packet)

				# Also have node send RD message for route back to source so update messages can be routed.
				new_pkts_rd, _ = self.generate_route_discover_packets(dst=msg.src, ts=ts, neighbors_filter={packet.current_node})
				new_pkts.extend(new_pkts_rd)

			elif self.name not in msg.rt and self.rd_responded[msg.src].get(rt_name, -C.ECR_RD_Timeout) < ts - C.ECR_RD_Timeout:
				# We have not seen similar message. Forward to all neighbors.
				self.rd_responded[msg.src][rt_name] = ts
				neighbors_sent = {packet.current_node}
				for _, entries in self.rmt.items():
					for next_hop, _, _ in entries:
						if next_hop not in neighbors_sent:
							discovery_msg = PT.ERC_RD(src=msg.src, dst_desired=msg.dst, route=msg.rt)
							discovery_msg.rt.append(self.name)  # Make sure to append self to route.
							pkt = PT.Packet(current_node=self.name, next_hop=next_hop, msg=discovery_msg, sent_ts=ts)
							new_pkts.append(pkt)
							neighbors_sent.add(next_hop)

		elif packet.type == 'RR':
			assert msg.rt and msg.rt[-1] == self.name, "Ill-formed RR message!"
			# Handle route response message. We update the values in the message and add/update entry in the RMT.
			lat_r, df = self.update_or_create_rmt_entry(dst=msg.dst, next_hop=packet.current_node, lat_r=msg.lat, df=msg.discount, ts=ts)
			msg.lat = lat_r
			msg.discount = df
			msg.rt.pop()

			# Forward along if needed.
			if msg.rt:
				pkt = PT.Packet(current_node=self.name, next_hop=msg.rt[-1], msg=msg, sent_ts=packet.sent_ts)
				new_pkts.append(pkt)

		elif packet.type == 'RP':
			rt_name = H.get_route_name(src=msg.src, dst=msg.dst)

			# Handle route packet message.
			if msg.dst == self.name:
				# Packet reach destination.
				self.num_rp_received[msg.src] += 1
				self.rp_received[rt_name].append((ts, packet.current_node))
				log.write("  Node [{}] got pkt [{}] from source [{}] with previous hop [{}].".format(self.name, msg.payload, msg.src, packet.current_node), is_packet=True)

			else:
				# Packet has not yet reached destination
				next_hop, rmt_lat_r, rmt_df = self.get_best_route(msg.dst)
				if next_hop:
					# Computed updated the lat_r and discount based on (Eq. 5).
					lat_r_updated = (ts + ((rmt_lat_r - ts) / C.ECR_gamma)) if rmt_df > 0 else rmt_lat_r
					df_updated = min(rmt_df - 1, 0)

					# Check if updates match expected values.
					if df_updated != msg.discount or lat_r_updated < msg.lat:
						# Detected unexpected information. Send back updated route information.
						# Only send back information if we have not done so recently.
						prev_update_ts = self.ru_in_flight[rt_name]
						if self.rmt[msg.src] and 0 <= prev_update_ts <= ts - C.ECR_RU_MinInterval:
							log.write("  Node [{}] has updated information on route from [{}] to [{}]. Sending back RU message".format(self.name, msg.src, msg.dst))
							self.ru_in_flight[rt_name] = ts

							# Send update along all possible route back to source.
							for update_next_hop, _, _ in self.rmt[msg.src]:
								update_msg = PT.ERC_RU(update_src=self.name, route_src=msg.src, route_dst=msg.dst, updated_discount_factor=rmt_df, updated_lat_r=rmt_lat_r)
								pkt = PT.Packet(current_node=self.name, next_hop=update_next_hop, msg=update_msg, sent_ts=ts)
								new_pkts.append(pkt)
					# Update values in message and forward packet.
					msg.lat = lat_r_updated
					msg.discount = df_updated
					pkt = PT.Packet(current_node=self.name, next_hop=next_hop, msg=msg, sent_ts=packet.sent_ts)
					new_pkts.append(pkt)

					log.write("  Node [{}] forwarding pkt [{}] from [{}] to [{}] with next hop [{}].".format(self.name, msg.payload, msg.src, msg.dst, pkt.next_hop), is_packet=True)

				else:
					# No route to destination. Send back error message.
					re_msg = PT.ERC_RE(error_src=self.name, route_src=msg.src, route_dst=msg.dst, error_code=msg.payload)
					pkt = PT.Packet(current_node=self.name, next_hop=packet.current_node, msg=re_msg, sent_ts=ts)
					new_pkts.append(pkt)

		elif packet.type == 'RU':
			# Handle route update message. Add updated values to rmt table.
			lat_r, df = self.update_or_create_rmt_entry(dst=msg.dst_route, next_hop=packet.current_node, lat_r=msg.lat, df=msg.discount, ts=ts)
			# Update msg and continue onwards if necessary.
			if msg.src_route != self.name:
				assert self.rmt[msg.src_route], "No path back to source to send update! This should not happen"
				msg.lat = lat_r
				msg.discount = df
				for next_hop, _, _ in self.rmt[msg.src_route]:
					pkt = PT.Packet(current_node=self.name, next_hop=next_hop, msg=msg, sent_ts=ts)
					new_pkts.append(pkt)

		elif packet.type == 'RE':
			# Handle route error message.
			if self.name == msg.src:
				assert msg.rt, 'Ill-formed RE message!'

				# This is the source node. Remove route with error from rmt.
				self.rmt[msg.dst] = [e for e in self.rmt[msg.dst] if e[0] != packet.current_node]
				log.write("  Node [{}] got route error message for pkt [{}] to [{}]. The error originated from [{}]. Will reattempt to send the packet through another route".format(self.name, msg.code, msg.dst, msg.rt[-1]), is_error=True)

				# Try and resend package.
				self.attempt_to_send_packet(msg.dst, ts, log, msg_num=msg.code)

			else:
				# Forward error message back towards source.
				next_hop, _, _ = self.get_best_route(msg.src)
				if next_hop:
					msg.rt.append([self.name])
					pkt = PT.Packet(current_node=self.name, next_hop=next_hop, msg=msg, sent_ts=packet.sent_ts)
					new_pkts.append(pkt)

		else:
			assert False, "Unknown message type!"

		# Keep track of how packets node has forwarded for the lat_n estimate.
		self.p_sample += len(new_pkts)

		return new_pkts, had_err

	# Overload of equals that looks at name only.
	def __eq__(self, other):
		return self.name == (other if isinstance(other, str) else other.name)

	# Hash function based on name.
	def __hash__(self):
		return hash(self.name)

	# String representation.
	def __str__(self):
		return '[{}: Loc{} Bat[{}] Links{}]'.format(self.name, self.xy, self.battery, self.links)

	# String representation.
	def __repr__(self):
		return str(self)
