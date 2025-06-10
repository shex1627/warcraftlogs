#!/usr/bin/env python3
"""
Setup script for the Warcraft Logs API client.
"""

from setuptools import setup, find_packages

setup(
    name="warcraftlogs",
    version="0.1.0",
    description="Python client for the Warcraft Logs API",
    author="Your Name",
    author_email="shicheng1627@gmail.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.0",
        "mcp[cli]"
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)