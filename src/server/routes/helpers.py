"""Module providing helper functions for endpoints."""

import uuid
from typing import Any

import numpy as np


def get_unique_identifier() -> str:
    """
    Generate a unique identifier string.
    
    :return: unique identifier as a string
    """
    return str(uuid.uuid4())


def bits_to_hex(bits: np.ndarray) -> str:
    """
    Convert 512-bit numpy array (shape (512,)) or (1, 512) of 0/1 ints into a 
    reversible 128-character hexadecimal string.
    
    :param bits: numpy array of shape (512,) or (1, 512) with values 0 or 1
    :return: hexadecimal string representation
    :raises ValueError: if input shape is incorrect
    """
    # Flatten in case the shape is (1, 512)
    flat = bits.reshape(-1)

    if flat.shape[0] != 512:
        raise ValueError("Input array must have shape (512,) or (1, 512)")
    
    bitstring = "".join(str(int(b)) for b in flat)  # 512 characters
    hexstr = hex(int(bitstring, 2))[2:].zfill(128)  # 128-char hex
    return hexstr


def hex_to_bits(hexstr: str) -> np.ndarray:
    """
    Convert a 128-character hexadecimal string back into a 512-bit numpy array 
    of shape (512,) with 0/1 ints.
    
    :param hexstr: hexadecimal string representation
    :return: numpy array of shape (512,) with values 0 or 1
    :raises ValueError: if input string length is incorrect
    """
    if len(hexstr) != 128:
        raise ValueError("Input hexadecimal string must be 128 characters long")
    
    bit_int = int(hexstr, 16)
    bitstring = bin(bit_int)[2:].zfill(512)  # binary string of length 512
    return np.array([int(b) for b in bitstring], dtype=np.int8)


def kmerize_sequence(sequence: list[Any], k: int) -> list[list[Any]]:
    """
    Generate k-mers from a given sequence (forward and backward).
    
    :param sequence: list of elements (e.g., amino acids)
    :param k: length of each k-mer
    :return: list of k-mer strings
    """
    kmers = []
    seq_length = len(sequence)
    
    # Forward k-mers
    for i in range(seq_length - k + 1):
        kmer = sequence[i:i + k]
        kmers.append(kmer)
    
    # Backward k-mers
    for i in range(seq_length - k, -1, -1):
        kmer = sequence[i:i + k]
        kmers.append(kmer)
    
    return kmers
