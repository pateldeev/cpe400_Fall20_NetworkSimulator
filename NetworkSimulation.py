from collections import defaultdict

import Constants as C
import Helper as H

import arcade as arc


# Logging class to help make it easier to log data to files and terminal
class NetworkLogger:
    # Initialize logging files.
    def __init__(self, log_full_fn, log_packets_fn, log_error_fn, log_performance_fn):
        self.log_full = open(log_full_fn, 'w')
        self.log_packets = open(log_packets_fn, 'w')
        self.log_error = open(log_error_fn, 'w')
        self.log_performance = open(log_performance_fn, 'w')

        self.pkt_buffer = []
        self.num_errors = 0

    # Log information to various logs.
    def write(self, log_str, is_full=True, is_packet=False, is_error=False, is_performance=False):
        if is_full:
            print(log_str)
            self.log_full.write(log_str + '\n')
        if is_packet:
            self.log_packets.write(log_str + '\n')
            self.pkt_buffer.append(log_str)
            if len(self.pkt_buffer) > C.PKT_INFO_MAX_LINES:
                self.pkt_buffer.pop(0)
        if is_error:
            self.log_error.write(log_str + '\n')
            if not log_str.startswith("ts:"):
                self.num_errors += 1
        if is_performance:
            self.log_performance.write(log_str + '\n')

    # Destructor for file cleanup
    def __del__(self):
        self.log_performance.close()
        self.log_error.close()
        self.log_packets.close()
        self.log_full.close()


# Class to hold simulation.
class NetworkSimulation(arc.Window):
    # Initialize simulation world.
    def __init__(self, world_size, screen_size, log_files):
        # Initialize world and screen sizes.
        self.world_width, self.world_height = world_size
        self.screen_width, self.screen_height = screen_size
        assert 0 < self.screen_width <= self.world_width and 0 < self.screen_height <= self.world_height

        # Move speed.
        self.move_speed = C.MOVE_SPEED_DEFAULT

        # Simulation time and auto step variables.
        self.ts = -1
        self.needs_update = False
        self.auto_step = False
        self.auto_step_speed = C.AUTO_SIM_DEFAULT_SPEED
        self.auto_step_ts = 0

        # Variables to hold network nodes and the rectangles and links that need to be drawn.
        self.nodes, self.node_rectangles, self.node_links = {}, {}, {}

        # Variables dealing with simulation of packets.
        self.pkts_schedule = []
        self.pkts_schedule_original_copy = []
        self.pkts_inflight = []

        # Holds a list of the network energy at every simulation time.
        self.network_energy = []
        self.network_energy_nodes = defaultdict(list)

        # Create logger.
        self.log = NetworkLogger(*log_files)

        # Variables for information text.
        self.text_info = "Sim ts: [{}]\n\n" \
                         "Step Forward: 'N'\nToggle Auto Step: 'A'\nAuto Step Speed: '[' / ']' [{}]\n\n" \
                         "Move Around: Arrow Keys\nMove Speed: '=' / '-' [{}]\n\n" \
                         "Show node info: Click on node\nShow simulation packets being sent: 'S' [{}]\n\n" \
                         "Exit: ESC/Q"
        self.text_node_info = ["Click on node to display info here!"]
        self.text_packets = ["Press 'S' to show packet info!"]
        self.show_packet_log = False

        # Initialize arcade backend.
        super().__init__(self.screen_width, self.screen_height, 'Network Simulation')
        self.set_viewport(0, self.screen_width, 0, self.screen_height)
        arc.set_background_color(arc.color.WHITE)

    # Setup network.
    def setup_network(self):
        # Create dictionary of rectangles that need drawing (to represent each node).
        for node_name, node in self.nodes.items():
            x, y = node.xy
            s = C.NODE_RECT_SIZE / 2
            # Rectangles for nodes.
            self.node_rectangles[node_name] = (node.xy, [(x - s, y - s),  # Bottom Left
                                                         (x + s, y - s),  # Bottom Right
                                                         (x - s, y + s),  # Top Left
                                                         (x + s, y + s),  # Top Right
                                                         ])
        # Create dictionary of node links that need drawing.
        for node_name, node in self.nodes.items():
            for neighbor_name in node.links:
                link_name = H.get_link_name(node_name, neighbor_name)
                if link_name not in self.node_links:
                    node_center, node_corners = self.node_rectangles[node_name]
                    neighbor_center, neighbor_corners = self.node_rectangles[neighbor_name]

                    # Pick points to draw links to/from.
                    def node_dist(p): return H.distance(p, neighbor_center)
                    def neighbor_dist(p): return H.distance(p, node_center)
                    node_corners_nearest = sorted(node_corners, key=node_dist)
                    neighbor_corners_nearest = sorted(neighbor_corners, key=neighbor_dist)
                    n1, n2 = node_corners_nearest[:2]
                    node_link_corner = n1 if abs(node_dist(n1) - node_dist(n2)) > 1.0 else H.average(n1, n2)
                    n1, n2 = neighbor_corners_nearest[:2]
                    neighbor_link_corner = n1 if abs(neighbor_dist(n1) - neighbor_dist(n2)) > 1.0 else H.average(n1, n2)
                    self.node_links[link_name] = (node_link_corner, neighbor_link_corner)

    # Sets up simulation network.
    def setup(self, network_nodes, sim_packets):
        # Nodes.
        for node_name, node in network_nodes.items():
            x, y = node.xy
            assert 0 < x < self.world_width and 0 < y < self.world_height
            assert '_' not in node_name, 'Name cannot have an underscore!'
        self.nodes = network_nodes

        # Simulation packet schedule. Sorted so packets to be sent now are at front of list.
        self.pkts_schedule = sorted(sim_packets, key=lambda p: p[0], reverse=True)
        self.pkts_schedule_original_copy = self.pkts_schedule.copy()

        # Current packets in flight
        self.pkts_inflight = []

        # Setup network
        self.setup_network()

    # Run simulation.
    def run(self):
        # Keep the window open until the user hits the 'close' button.
        arc.run()

    # Draws network nodes and links.
    def draw_network(self):
        # Draw nodes.
        for node_name, ((x, y), _) in self.node_rectangles.items():
            node_battery = self.nodes[node_name].battery
            arc.draw_rectangle_outline(x, y, C.NODE_RECT_SIZE, C.NODE_RECT_SIZE, arc.color.BLUE, 1)

            # Draw battery level. Show dead nodes as full red.
            if node_battery == 0.0:
                arc.draw_rectangle_filled(x, y, C.NODE_RECT_SIZE, C.NODE_RECT_SIZE, arc.color.RED)
            else:
                arc.draw_rectangle_filled(x, y - (C.NODE_RECT_SIZE*(1-node_battery) / 2),
                                          C.NODE_RECT_SIZE, C.NODE_RECT_SIZE*node_battery,
                                          arc.color.GREEN if node_battery >= 0.2 else arc.color.YELLOW)

            # Label nodes.
            arc.draw_text('{}'.format(node_name), x, y, arc.color.BLACK, font_size=15, width=50, bold=True, align='center', anchor_x='center', anchor_y='center')

        # Draw links.
        for _, (start_xy, end_xy) in self.node_links.items():
            arc.draw_line(*start_xy, *end_xy, arc.color.BLACK, 2)

    # Draws information text.
    def draw_info_text(self):
        vp_x_start, vp_x_end, vp_y_start, vp_y_end = self.get_viewport()

        # Simulation Info.
        x, y = vp_x_end - C.SIM_INFO_RECT_SIZE_W / 2, vp_y_end - C.SIM_INFO_RECT_SIZE_H / 2
        arc.draw_rectangle_filled(x, y, C.SIM_INFO_RECT_SIZE_W, C.SIM_INFO_RECT_SIZE_H, arc.color.WHITE)
        arc.draw_rectangle_outline(x, y, C.SIM_INFO_RECT_SIZE_W, C.SIM_INFO_RECT_SIZE_H, arc.color.BLACK, 1)
        arc.draw_text(self.text_info.format(self.ts, self.auto_step_speed, self.move_speed, self.show_packet_log),
                      x + 5 - C.SIM_INFO_RECT_SIZE_W / 2, y,
                      arc.color.BLACK, font_size=C.TEXT_SIZE, width=C.SIM_INFO_RECT_SIZE_W, bold=True, align='left', anchor_x='left', anchor_y='center')

        # Node info.
        x, y = vp_x_end - C.NODE_INFO_RECT_SIZE_W / 2, vp_y_end - C.NODE_INFO_RECT_SIZE_H / 2 - C.SIM_INFO_RECT_SIZE_H
        arc.draw_rectangle_filled(x, y, C.NODE_INFO_RECT_SIZE_W, C.NODE_INFO_RECT_SIZE_H, arc.color.WHITE)
        arc.draw_rectangle_outline(x, y, C.NODE_INFO_RECT_SIZE_W, C.NODE_INFO_RECT_SIZE_H, arc.color.BLACK, 1)
        arc.draw_text('\n'.join(self.text_node_info[-C.NODE_INFO_MAX_LINES:]),
                      x + 5 - C.NODE_INFO_RECT_SIZE_W / 2, y,
                      arc.color.BLACK, font_size=C.TEXT_SIZE, width=C.NODE_INFO_RECT_SIZE_W, bold=True, align='left', anchor_x='left', anchor_y='center')

        # Packet info.
        x, y = vp_x_end - C.PKT_INFO_RECT_SIZE_W / 2, vp_y_end - C.PKT_INFO_RECT_SIZE_H / 2 - C.SIM_INFO_RECT_SIZE_H - C.NODE_INFO_RECT_SIZE_H
        arc.draw_rectangle_filled(x, y, C.PKT_INFO_RECT_SIZE_W, C.PKT_INFO_RECT_SIZE_H, arc.color.WHITE)
        arc.draw_rectangle_outline(x, y, C.PKT_INFO_RECT_SIZE_W, C.PKT_INFO_RECT_SIZE_H, arc.color.BLACK, 1)
        arc.draw_text("Press 'S' to {} packet info!".format("hide" if self.show_packet_log else "show"),
                      x + 5 - C.PKT_INFO_RECT_SIZE_W / 2, y,
                      arc.color.BLACK, font_size=C.TEXT_SIZE, width=C.PKT_INFO_RECT_SIZE_W, bold=True, align='left',
                      anchor_x='left', anchor_y='center')
        if self.show_packet_log:
            x, y = vp_x_start + C.PKT_INFO_EXPANDED_RECT_SIZE_W / 2, vp_y_start + C.PKT_INFO_EXPANDED_RECT_SIZE_H / 2
            arc.draw_rectangle_filled(x, y, C.PKT_INFO_EXPANDED_RECT_SIZE_W, C.PKT_INFO_EXPANDED_RECT_SIZE_H, arc.color.WHITE)
            arc.draw_rectangle_outline(x, y, C.PKT_INFO_EXPANDED_RECT_SIZE_W, C.PKT_INFO_EXPANDED_RECT_SIZE_H, arc.color.BLACK, 1)
            self.text_packets = self.log.pkt_buffer
            arc.draw_text('\n'.join(self.text_packets[-C.PKT_INFO_MAX_LINES:]),
                          x + 5 - C.PKT_INFO_EXPANDED_RECT_SIZE_W / 2, y,
                          arc.color.BLACK, font_size=C.TEXT_SIZE_DETAILED, width=C.PKT_INFO_EXPANDED_RECT_SIZE_W, bold=True, align='left', anchor_x='left', anchor_y='center')

    # Draw updated callback.
    def on_draw(self):
        arc.start_render()

        self.draw_network()
        self.draw_info_text()

    # Maintains nodes and links.
    # Each node updates its lat estimate and sends to neighbors if enough time has passed.
    def maintain_nodes_and_links(self):
        # We update estimates every time-step. We update links to neighbors every other time-step as per ECR protocol.
        update_estimates = True
        update_links = (self.ts % 2 == 0)

        for n_name, n in self.nodes.items():
            # Progress node.
            n.progress(self.ts, update_estimates)

            # Have each node send lat to neighbors if link maintenance is to be performed.
            if update_links:
                if not n.is_alive():
                    for neighbor_name in n.links:
                        self.nodes[neighbor_name].cleanup_dead_neighbor(n_name)
                else:
                    for neighbor_name in n.links:
                        neighbor = self.nodes[neighbor_name]
                        if neighbor.is_alive():
                            # Have each node update its neighbor and vise versa.
                            n.update_or_create_rmt_entry(dst=neighbor_name, next_hop=neighbor_name, lat_r=neighbor.lat, df=0, ts=self.ts)
                            neighbor.update_or_create_rmt_entry(dst=n_name, next_hop=n_name, lat_r=n.lat, df=0, ts=self.ts)

    # Update in-flight packets.
    def update_packets(self):
        # Handle all in-flight packets. Add any newly generated packets as well.
        new_inflight = []
        for pkt in self.pkts_inflight:
            new_inflight_tmp, had_err = self.nodes[pkt.next_hop].handle_packet(pkt, self.ts, self.log)
            new_inflight.extend(new_inflight_tmp)
            if had_err:
                self.log.write("   ERROR: Could not handle in-flight [{}] message at node [{}]!".format(pkt, pkt.next_hop), is_error=True)
        self.pkts_inflight = new_inflight

    # Attempt to send scheduled packets
    def attempt_scheduled_send(self):
        if not self.pkts_schedule:
            self.log.write("  No packets left to send! All required packets are in in-flight.")
            return

        # Try and send each packet that needs to be sent.
        schedule_updated = []
        while self.pkts_schedule and self.pkts_schedule[-1][0] == self.ts:
            ts, src, dst, num = self.pkts_schedule[-1]

            # Try and send packet.
            new_inflight, packet_sent, error = self.nodes[src].attempt_to_send_packet(dst, ts, self.log)
            if error:
                self.log.write("  ERROR: Node [{}] cannot route packets to [{}]! The node may be offline or unreachable! Any future packets to this destination will not be sent!".format(src, dst), is_error=True)
                num = 0
            else:
                self.pkts_inflight.extend(new_inflight)
                if packet_sent:
                    # Packet was sent.
                    num -= 1

            # Add new number to updated schedule for the next time-step.
            if num != 0:
                schedule_updated.append((ts + 1, src, dst, num))
            self.pkts_schedule.pop()

        self.pkts_schedule.extend(schedule_updated)

    # Update callback.
    def update(self, delta_time):
        # Handle auto stepping.
        if self.auto_step:
            self.auto_step_ts -= delta_time
            if self.auto_step_ts <= 0:
                self.needs_update = True
                self.auto_step_ts = 1 / self.auto_step_speed

        # Update network.
        if self.needs_update:
            self.ts += 1
            self.log.write("ts: [{:05d}]  In-Flight at start [{}]".format(self.ts, len(self.pkts_inflight)), is_full=True, is_packet=True, is_error=True)

            print('Schedule: ', self.pkts_schedule)
            print('Flight: ', self.pkts_inflight)

            # Update and maintain links.
            # Each node updates its lat estimate and passes it to neighbors.
            self.log.write("\nUpdating nodes and maintaining links if needed".format(self.ts))
            self.maintain_nodes_and_links()

            # Update inflight packets.
            # Nodes on the receiving end of packets sent at previous ts handle them and create new packets in response.
            self.log.write("\nUpdating the [{}] in-flight packets".format(len(self.pkts_inflight)))
            self.update_packets()

            # Send simulation packets.
            # We try and send the packets that simulate application layer requests.
            self.log.write("\nAttempting to send the required simulation packets")
            self.attempt_scheduled_send()

            # Update energy history.
            self.network_energy.append(sum(n.battery for _, n in self.nodes.items()) / len(self.nodes))
            for n_name, n in self.nodes.items():
                self.network_energy_nodes[n_name].append(n.battery)

            print('\nSchedule: ', self.pkts_schedule)
            print('Flight: ', self.pkts_inflight)

            # Update is done. Wait until next ts.
            self.needs_update = False
            self.log.write("\nDone updating: there are now [{}] in-flight packets.".format(len(self.pkts_inflight)))
            self.log.write("||||||||||||||||||||||||||||||||||")

            # Close simulation if we are done.
            if not(self.pkts_schedule or self.pkts_inflight) or all(not n.is_alive() for _, n in self.nodes.items()):
                self.cleanup_and_close()

    # Cleanup and close simulation. Print performance stats to logs.
    def cleanup_and_close(self, is_forced=False):
        # Print details of why simulation ended.
        if is_forced:
            self.log.write("Closing simulation based on user request!", is_performance=True)
        elif not(self.pkts_schedule or self.pkts_inflight):
            self.log.write("Simulation done! All simulated packets have been delivered.", is_performance=True)
        else:
            self.log.write("Simulation done! Enough network nodes are dead that packets can no longer be routed as required.", is_performance=True)

        # Log simulation packet stats.
        for t, src, dst, cnt in self.pkts_schedule_original_copy:
            rt_name = H.get_route_name(src, dst)

            # Display link information
            if cnt < 0:
                log_str = "\nAt [{:05d}] Node [{}] was requested to send as many packets as possible to Node [{}]".format(t, src, dst)
            else:
                log_str = "\nAt [{:05d}] Node [{}] was requested to send [{}] packets to Node [{}]".format(t, src, cnt, dst)
            self.log.write(log_str, is_full=False, is_performance=True)

            # Display sent information.
            self.log.write("  Node [{}] sent [{}] packets (including any necessary retries)".format(src, self.nodes[src].num_rp_sent[dst]), is_full=False, is_performance=True)
            rp_sent = self.nodes[src].rp_sent[rt_name]
            rp_sent_end_times = defaultdict(int)
            log_strs = []
            for i, (t_start, next_hop) in enumerate(rp_sent):
                if rp_sent_end_times[next_hop] > t_start:
                    continue

                t_end = t_start
                rp_cnt = 0
                j = i + 1
                while j < len(rp_sent):
                    if rp_sent[j][0] > t_end + 1:
                        break

                    if rp_sent[j][1] == next_hop:
                        t_end += 1
                        rp_cnt += 1

                    j += 1
                rp_sent_end_times[next_hop] = t_end + 1
                log_strs.append("    ts: [{:05d}]-[{:05d}]: [{}] sent [{}] packets through [{}]".format(t_start, t_end, src, rp_cnt, next_hop))
            for s in sorted(log_strs):
                self.log.write(s, is_full=False, is_performance=True)

            # Display received information.
            self.log.write("  Node [{}] received [{}] packets".format(dst, self.nodes[dst].num_rp_received[src]), is_full=False, is_performance=True)
            rp_received = self.nodes[dst].rp_received[rt_name]
            rp_received_end_times = defaultdict(int)
            log_strs = []
            for i, (t_start, prev_hop) in enumerate(rp_received):
                if rp_received_end_times[prev_hop] > t_start:
                    continue

                t_end = t_start
                rp_cnt = 0
                j = i + 1
                while j < len(rp_received):
                    if rp_received[j][0] > t_end + 1:
                        break

                    if rp_received[j][1] == prev_hop:
                        t_end += 1
                        rp_cnt += 1

                    j += 1
                rp_received_end_times[prev_hop] = t_end + 1
                log_strs.append("    ts: [{:05d}]-[{:05d}]: [{}] received [{}] packets via [{}]".format(t_start, t_end, dst, rp_cnt, prev_hop))
            for s in sorted(log_strs):
                self.log.write(s, is_full=False, is_performance=True)

        # Log energy history.
        self.log.write("\nEnergy History:", is_full=False, is_performance=True)
        for i, e in enumerate(self.network_energy):
            self.log.write("  [{:05d}] [{:.5f}]".format(i + 1, e), is_full=False, is_performance=True)

        with open('energy.txt', 'w') as f:
            for e in self.network_energy_nodes['A']:
                f.write("{:.5f}\n".format(e))

        # Close the window and cleanup.
        arc.close_window()

    def on_key_press(self, symbol, modifiers):
        pass

    # Handle various keybinds for simulation environment.
    def on_key_release(self, symbol, modifiers):
        if modifiers == C.MODIFIER_NO:
            if symbol == arc.key.ESCAPE or symbol == arc.key.Q:
                # Quit simulation.
                self.cleanup_and_close(is_forced=True)
            elif symbol in [arc.key.UP, arc.key.DOWN, arc.key.RIGHT, arc.key.LEFT]:
                # Move around in simulation world.
                x, y = 0, 0
                if symbol == arc.key.UP:
                    y = 1
                elif symbol == arc.key.DOWN:
                    y = -1
                elif symbol == arc.key.RIGHT:
                    x = 1
                elif symbol == arc.key.LEFT:
                    x = -1
                else:
                    assert False

                # Update viewport.
                vp = self.get_viewport()
                vp_new_x = H.clamp(vp[0] + x * self.move_speed, 0, self.world_width - self.screen_width)
                vp_new_y = H.clamp(vp[2] + y * self.move_speed, 0, self.world_height - self.screen_height)
                self.set_viewport(vp_new_x, vp_new_x + self.screen_width, vp_new_y, vp_new_y + self.screen_height)

            elif symbol == arc.key.N:
                # Manually step forward in simulation.
                self.auto_step = False
                self.needs_update = True
            elif symbol == arc.key.A:
                # Automatically step forward in simulation.
                self.auto_step = not self.auto_step

            elif symbol == arc.key.EQUAL:
                # Increase move speed.
                self.move_speed += C.MOVE_SPEED_CHANGE_RATE
            elif symbol == arc.key.MINUS:
                # Decrease move speed.
                self.move_speed -= C.MOVE_SPEED_CHANGE_RATE

            elif symbol == arc.key.BRACKETRIGHT:
                # Increase auto-simulation speed.
                self.auto_step_speed *= 2
            elif symbol == arc.key.BRACKETLEFT:
                # Decrease auto-simulation speed.
                self.auto_step_speed /= 2

            elif symbol == arc.key.S:
                # Show packets text.
                self.show_packet_log = not self.show_packet_log

            else:
                self.log.write("INFO: Unused key released: [{}]".format(symbol))

    def on_mouse_drag(self, x, y, dx, dy, _buttons, _modifiers):
        pass

    def on_mouse_motion(self, x, y, dx, dy):
        pass

    def on_mouse_press(self, x, y, button, modifiers):
        pass

    # Allow for user to click on nodes.
    def on_mouse_release(self, x, y, button, modifiers):
        if modifiers == C.MODIFIER_NO:
            # Check if we clicked on node.
            if button == arc.MOUSE_BUTTON_LEFT:
                x_offset, _, y_offset, _ = self.get_viewport()
                x_world, y_world = x + x_offset, y + y_offset
                for node_name, (_, [(bl_x, bl_y), _, _, (tr_x, tr_y)]) in self.node_rectangles.items():
                    if bl_x <= x_world <= tr_x and bl_y <= y_world <= tr_y:
                        # Node was clicked on print information.
                        self.log.write("\nPrinting stats for node [{}]".format(node_name))
                        node = self.nodes[node_name]
                        info_txt = ["\n  Battery Level: [{:.7f}]".format(node.battery),
                                    "  LAT_n: [{:.7f}]".format(node.lat),
                                    "\n  P_Sample: [{:.7f}]".format(node.p_sample),
                                    "  P_Hat: [{}]".format(node.p_hat),
                                    "\n  RMT\n    (dst, next-hop, lat_r, d_f):",
                                    ]
                        if not node.rmt:
                            info_txt.append("    RMT is empty!")
                        else:
                            node.sort_rmt()
                            for dst, entries in sorted(node.rmt.items()):
                                for next_hop, lat_r, d_f in entries:
                                    info_txt.append("    [{}] [{}] [{:.5f}] [{:.5f}]".format(dst, next_hop, lat_r, d_f))

                        # Log and display text.
                        for t in info_txt:
                            self.log.write(t)
                        self.text_node_info = ["Node [{}] info at ts [{}]".format(node_name, self.ts)]
                        self.text_node_info.extend(info_txt)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        pass
