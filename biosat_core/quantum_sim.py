import random, numpy as np
from math import log2

def random_bits(n): return [random.randint(0,1) for _ in range(n)]
def random_bases(n): return [random.choice(['Z','X']) for _ in range(n)]

def bin_entropy(p):
    if p <= 0 or p >= 1: return 0.0
    return -p*np.log2(p) - (1-p)*np.log2(1-p)

def transmit_bb84(n_photons, trans_prob, error_prob):
    a_bits = random_bits(n_photons)
    a_bases = random_bases(n_photons)
    arrives = np.random.rand(n_photons) < trans_prob
    b_bases = random_bases(n_photons)
    b_results = [None]*n_photons
    for i in range(n_photons):
        if not arrives[i]:
            b_results[i] = None; continue
        if a_bases[i] == b_bases[i]:
            bit = a_bits[i]
            if random.random() < error_prob:
                bit ^= 1
            b_results[i] = bit
        else:
            b_results[i] = random.randint(0,1)
    sifted_indices = [i for i in range(n_photons) if arrives[i] and a_bases[i]==b_bases[i]]
    a_sift = [a_bits[i] for i in sifted_indices]
    b_sift = [b_results[i] for i in sifted_indices]
    sample_size = max(1, int(0.2 * len(a_sift))) if a_sift else 0
    if sample_size > 0 and len(a_sift) >= sample_size:
        sample_idx = random.sample(range(len(a_sift)), sample_size)
        errors = sum(1 for k in sample_idx if a_sift[k] != b_sift[k])
        qber = errors / sample_size
    else:
        qber = 0.0
    leak_ec = 0.1
    R_secure = max(0, int(len(a_sift) * max(0.0, 1 - bin_entropy(qber) - leak_ec)))
    sifted_key = ''.join(str(b) for b in b_sift)
    demo_key = sifted_key[:R_secure]
    return {"n_sent": n_photons, "n_sifted": len(a_sift), "qber": qber, "R_secure_bits": R_secure, "sifted_key": demo_key}

def trans_prob_from_distance(d_km, loss_coeff=0.0012):
    return float(np.exp(-loss_coeff * d_km))

def entanglement_fidelity(trans_prob, depolar_prob=0.05):
    survive = trans_prob**2
    fidelity = survive*(1-depolar_prob) + (1-survive)*0.5
    return float(np.clip(fidelity, 0.0, 1.0))
