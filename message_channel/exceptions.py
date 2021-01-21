class ChannelError(Exception):
    """Base error of channel"""


class ChannelClosedError(ChannelError):
    """Error raised when channel is closed"""


class ChannelAlreadyOpenedError(ChannelError):
    """Error raised when channel is already opened"""
