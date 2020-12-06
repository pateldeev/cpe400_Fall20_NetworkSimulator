# Indicates no special key pressed (ex: shift, ctr).
MODIFIER_NO = 16

# Move speed for arrow keys.
MOVE_SPEED_DEFAULT = 250
MOVE_SPEED_CHANGE_RATE = 20

# Size of node rectangle.
NODE_RECT_SIZE = 40

# Size of info text boxes.
SIM_INFO_RECT_SIZE_H = 350
SIM_INFO_RECT_SIZE_W = 850
NODE_INFO_RECT_SIZE_H = 600
NODE_INFO_RECT_SIZE_W = 600
NODE_INFO_MAX_LINES = 24
PKT_INFO_RECT_SIZE_H = 100
PKT_INFO_RECT_SIZE_W = 600
PKT_INFO_EXPANDED_RECT_SIZE_H = 450
PKT_INFO_EXPANDED_RECT_SIZE_W = 1300
PKT_INFO_MAX_LINES = 20
TEXT_SIZE = 23
TEXT_SIZE_DETAILED = 20

# Auto step speed.
AUTO_SIM_DEFAULT_SPEED = 16

# ECR Algorithm parameters. See associated paper for full details on what they represent.
ECR_d_c = 0.001  # Constant battery drainage factor
ECR_d_p = 0.0003  # Variable battery drainage factor per packet.
ECR_alpha = 0.8  # Weight of historical value for EMA of packets sent.
ECR_gamma = 0.98  # Discount factor for times.
ECR_RD_Timeout = 100  # If route is still not found after 100 time-steps, an error has occurred.
ECR_RD_Resend = 10  # After this many packets are sent along a specific route, the sending node will send out another round of RD packets to get updated information along any known suboptimal routes.
ECR_RU_MinInterval = 5  # Minimum interval a node must wait before sending update messages for a given route again.
