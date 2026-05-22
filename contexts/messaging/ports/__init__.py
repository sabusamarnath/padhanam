"""Messaging ports layer (D129).

Abstractions the application layer depends on: ``MessageRepository``
for persistence and ``MessageDeliveryPort`` for outbound vendor
send. Ports are pure per D16 — stdlib plus shared_kernel only.
"""
