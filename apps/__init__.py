"""Independently runnable product apps.

The product apps are deployment entrypoints. Shared behavior stays in
`shared_platform` so the apps can diverge by product without duplicating the
beta6 runtime, citation contract, or static serving policy.
"""
