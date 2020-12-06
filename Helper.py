import math

from NetworkNode import NetworkNode


# Clamp value between bounds.
def clamp(n, bound_lower, bound_upper):
	return max(bound_lower, min(n, bound_upper))


# Get unique "link name" between any two nodes.
def get_link_name(node1, node2):
	return min(node1, node2) + '_' + max(node1, node2)


# Separate "link name" to get names of node.
def get_links(link_name):
	return link_name.split('_')


# Get unique "route name" between any two nodes.
def get_route_name(src, dst):
	return src + '_' + dst


# Separate "route name" to get names of source and destination node.
def get_route_nodes(route_name):
	return route_name.split('_')


# Distance between points.
def distance(p1, p2):
	return math.sqrt(((p1[0] - p2[0]) ** 2) + ((p1[1] - p2[1]) ** 2))


# Average two points.
def average(p1, p2):
	return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2


# Generate valid lines in a file.
def gen_file_lines(f_n):
	with open(f_n, 'r') as f:
		for ln in f.readlines():
			ln = ln.strip()
			if not ln or ln.startswith('#'):
				continue
			yield ln


# Load nodes from file.
# Returns dictionary from node name to object of NetworkNode.
def load_nodes(f_n):
	nodes_dict = {}

	for ln in gen_file_lines(f_n):
		ln_items = ln.split(' ')
		if len(ln_items) == 2:
			# Read link between nodes.
			n_1, n_2 = ln_items
			nodes_dict[n_1].links.add(n_2)
			nodes_dict[n_2].links.add(n_1)

		elif len(ln_items) == 4:
			# Read node name and location
			n, x, y, b = ln_items
			nodes_dict[n] = NetworkNode(n, (int(x), int(y)), float(b))
		else:
			assert False, 'Check nodes input file format!'

	return nodes_dict


# Load packets to send from file.
# Returns list: [(ts, src, dst, limit)].
def load_simulation_packets(f_n):
	pkts = []

	for ln in gen_file_lines(f_n):
		ln_items = ln.strip().split(' ')
		if len(ln_items) == 3:
			s, d, t = ln_items
			c = -1
		elif len(ln_items) == 4:
			s, d, t, c = ln_items
		else:
			assert False, 'Check packets input file format!'
		pkts.append((int(t), s, d, int(c)))

	return pkts
