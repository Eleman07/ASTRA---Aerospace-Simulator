"""ASTRA desktop SDK, independent of legacy local astra modules."""
from .client import AstraClient, CLIENT_VERSION
__all__=["AstraClient","CLIENT_VERSION"]
