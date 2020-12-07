import Constants as C

# Logging class to help make it easier to log data to files and terminal
class NetworkLogger:
    # Initialize logging files.
    def __init__(self, log_full_fn, log_packets_fn, log_error_fn, log_performance_fn, log_energy_fn):
        self.log_full = open(log_full_fn, 'w')
        self.log_packets = open(log_packets_fn, 'w')
        self.log_error = open(log_error_fn, 'w')
        self.log_performance = open(log_performance_fn, 'w')
        self.log_energy = open(log_energy_fn, 'w')

        self.pkt_buffer = []
        self.num_errors = 0

    # Log information to various logs.
    def write(self, log_str, is_full=True, is_packet=False, is_error=False, is_performance=False, is_energy=False):
        if is_full and not C.SPEED_UP_EXECUTION:
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
        if is_energy:
            self.log_energy.write(log_str + '\n')

    # Destructor for file cleanup.
    def __del__(self):
        self.log_energy.close()
        self.log_performance.close()
        self.log_error.close()
        self.log_packets.close()
        self.log_full.close()
