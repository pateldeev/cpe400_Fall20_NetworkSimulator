import argparse

import Helper as H
from NetworkSimulation import NetworkSimulation as NS

# Program arguments.
arg_parser = argparse.ArgumentParser(description='Simulates the ECR routing protocol.')
arg_parser.add_argument('--network_file', help='Path to network file defining nodes and links.', type=str, required=True)
arg_parser.add_argument('--packets_file', help='Path to packets file defining what packets should be simulated at what times.', type=str, required=True)
arg_parser.add_argument('--log_file_full', help='Output Log file', type=str, default='log_full.txt')
arg_parser.add_argument('--log_file_packets', help='Output Log file for simulation packets sent.', type=str, default='log_packets.txt')
arg_parser.add_argument('--log_file_errors', help='Output log file for errors.', type=str, default='log_errors.txt')
arg_parser.add_argument('--log_file_performance', help='Output Log file for performance.', type=str, default='log_perforamance.txt')
args = arg_parser.parse_args()

# Set constants for the screen and world size.
WORLD_SIZE = (5000, 5000)
SCREEN_SIZE = (1920, 1080)

if __name__ == '__main__':
    print('Starting Simulation')

    # Create simulation environment.
    log_files = (args.log_file_full, args.log_file_packets, args.log_file_errors, args.log_file_performance)
    ns = NS(WORLD_SIZE, SCREEN_SIZE, log_files)

    # Setup network.
    nodes_dict = H.load_nodes(args.network_file)
    sim_packets = H.load_simulation_packets(args.packets_file)
    ns.setup(nodes_dict, sim_packets)

    # Run simulation.
    ns.run()

    # Print some results.
    print('|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||')
    print('Simulation Done')
    print("Simulation lasted [{}] simulation time steps or [{}] secs in real time".format(ns.ts, ns.ts / 1000))
    print("There were [{}] instances of a handled error in routing packets!".format(ns.log.num_errors))
    print("\nFor details see the various log files:")
    print("  Full log file (contains terminal output):", log_files[0])
    print("  Packets log file (contains log of how simulation packets were sent/received):", log_files[1])
    print("  Errors log file (contains log of any errors handled by protocol):", log_files[2])
    print("  Performance log file (contains log of protocol performance data):", log_files[3])
