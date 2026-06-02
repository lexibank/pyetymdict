"""
Functionality related to the to-be-standardized EtymDict module.
"""
from .tree import reconstruction_tree
from .dataset import Dataset, Form, Language

assert reconstruction_tree and Dataset and Form and Language

__version__ = '1.0.1.dev0'
