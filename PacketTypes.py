# Defines the various packet types. See the associated paper for packet structure and purposes.


# Route Discovery.
class ERC_RD:
	def __init__(self, src, dst_desired, route):
		self.src = src
		self.dst = dst_desired
		self.rt = route.copy()


# Route Response.
class ERC_RR:
	def __init__(self, route_src, route_dst, discount_factor, lat_r, route):
		self.src = route_src
		self.dst = route_dst
		self.discount = discount_factor
		self.lat = lat_r
		self.rt = route.copy()


# Route Packet.
class ERC_RP:
	def __init__(self, src, dst, expected_discount_factor, expected_lat_r, payload):
		self.src = src
		self.dst = dst
		self.discount = expected_discount_factor
		self.lat = expected_lat_r
		self.payload = payload


# Route Update.
class ERC_RU:
	def __init__(self, update_src, route_src, route_dst, updated_discount_factor, updated_lat_r):
		self.src = update_src
		self.src_route = route_src
		self.dst_route = route_dst
		self.discount = updated_discount_factor
		self.lat = updated_lat_r


# Route Error.
class ERC_RE:
	def __init__(self, error_src, route_src, route_dst, error_code):
		self.src = route_src
		self.dst = route_dst
		self.code = error_code
		self.rt = [error_src]


# Packet wrapper. Holds current node, next hop, message, and sent time.
class Packet:
	def __init__(self, current_node, next_hop, msg, sent_ts):
		self.current_node = current_node
		self.next_hop = next_hop
		self.msg = msg
		self.sent_ts = sent_ts

		self.type = None
		if isinstance(msg, ERC_RD):
			self.type = 'RD'
		elif isinstance(msg, ERC_RR):
			self.type = 'RR'
		elif isinstance(msg, ERC_RP):
			self.type = 'RP'
		elif isinstance(msg, ERC_RU):
			self.type = 'RU'
		elif isinstance(msg, ERC_RE):
			self.type = 'RE'
		assert self.type, "Msg type is wrong!"

	# String representation
	def __str__(self):
		return '[{} Packet at {} with next hop {}]'.format(self.type, self.current_node, self.next_hop)

	# String representation
	def __repr__(self):
		return str(self)
