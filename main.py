import argparse

import Constants as C
import Helper as H
from NetworkSimulation import NetworkSimulation as NS

# Program arguments.
arg_parser = argparse.ArgumentParser(description='Simulates the ECR routing protocol.')
arg_parser.add_argument('--network_file', help='Path to network file defining nodes and links.', type=str, required=True)
arg_parser.add_argument('--packets_file', help='Path to packets file defining what packets should be simulated at what times.', type=str, required=True)
arg_parser.add_argument('--log_file_full', help='Output Log file', type=str, default='logs/log_full.txt')
arg_parser.add_argument('--log_file_packets', help='Output Log file for simulation packets sent.', type=str, default='logs/log_packets.txt')
arg_parser.add_argument('--log_file_errors', help='Output log file for errors.', type=str, default='logs/log_errors.txt')
arg_parser.add_argument('--log_file_performance', help='Output Log file for performance.', type=str, default='logs/log_performance.txt')
arg_parser.add_argument('--log_file_energy', help='Output Log file for energies.', type=str, default='logs/log_energy.txt')
args = arg_parser.parse_args()

if __name__ == '__main__':
    print('Starting Simulation')

    # Create simulation environment.
    log_files = (args.log_file_full, args.log_file_packets, args.log_file_errors, args.log_file_performance, args.log_file_energy)
    ns = NS(C.WORLD_SIZE, C.SCREEN_SIZE, log_files)

    # Setup network and get packets that need to be simulated.
    nodes_dict = H.load_nodes(args.network_file)
    sim_packets = H.load_simulation_packets(args.packets_file)
    ns.setup(nodes_dict, sim_packets)

    # Run simulation.
    ns.run()

    # Print results.
    print('|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||')
    print('Simulation Done!')
    print("Simulation lasted [{}] simulation time steps or [{}] secs in real time".format(ns.ts, ns.ts / 1000))
    print("There were [{}] instances of a handled error in routing packets.".format(ns.log.num_errors))
    print("\nFor details see the various log files:")
    print("  Full log file (contains terminal output):", log_files[0])
    print("  Packets log file (contains log of how individual simulation packets were sent, forwarded, and received):", log_files[1])
    print("  Error log file (contains log of any errors handled by the protocol. Includes necessary resending of packets):", log_files[2])
    print("  Performance log file (contains log of how packets were routed):", log_files[3])
    print("  Energy log file (contains log of average network energy at each simulation time-step):", log_files[4])
