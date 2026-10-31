"""Backward-compatible import for the independent ASTRA desktop SDK."""
from astra_sdk.client import AstraClient, CLIENT_VERSION
__all__=["AstraClient","CLIENT_VERSION"]
