#!/usr/bin/env python3
"""
cli-anything-clivoice - 醫療診斷輔助系統 CLI harness
"""

from setuptools import setup, find_namespace_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cli-anything-clivoice",
    version="1.0.0",
    author="SoapVoice Team",
    author_email="team@soapvoice.example.com",
    description="醫療診斷輔助系統 CLI harness - 整合 ICD10v2, medicalordertreeview, ATCcodeTW",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/soapvoice/clivoice",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    namespace_packages=["cli_anything"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "cachetools>=5.3.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-mock>=3.10.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cli-anything-clivoice=cli_anything.clivoice.cli.main:cli",
            "clivoice=cli_anything.clivoice.cli.main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "cli_anything.clivoice": [
            "data/*.json",
            "data/*.js",
            "config/*.yaml",
            "config/*.yml",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/soapvoice/clivoice/issues",
        "Source": "https://github.com/soapvoice/clivoice",
        "Documentation": "https://github.com/soapvoice/clivoice/wiki",
    },
)
