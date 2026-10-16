"""Inference helpers for the count-based portrait CA; no source photos needed."""
import torch


class CompactRows:
    """Exact lookup into occupied rows of a sparse count table, without densifying it.

    The original row count is retained for hashing. Unoccupied rows return zeros,
    so back-off decisions and seeded samples are identical to dense inference.
    """
    def __init__(self, table, device):
        self.shape = table.shape
        table = table.coalesce()
        rows, columns = table.indices()
        occupied, inverse = torch.unique_consecutive(rows, return_inverse=True)
        self.indices = occupied.to(device)
        self.values = torch.zeros((len(occupied) + 1, self.shape[1]), dtype=table.dtype)
        self.values[inverse, columns] = table.values()
        self.values = self.values.to(device)

    def __getitem__(self, keys):
        slots = torch.searchsorted(self.indices, keys.contiguous())
        safe = slots.clamp_max(max(0, len(self.indices) - 1))
        if len(self.indices):
            found = (slots < len(self.indices)) & (self.indices[safe] == keys)
            slots = torch.where(found, slots, len(self.indices))
        return self.values[slots]

    def add_(self, keys, colours):
        """Accumulate new integer observations while retaining original hash size."""
        keys, colours = keys.reshape(-1), colours.reshape(-1)
        rows, inverse = torch.unique(keys, sorted=True, return_inverse=True)
        updates = torch.zeros((len(rows), self.shape[1]), dtype=self.values.dtype, device=self.values.device)
        updates.view(-1).index_add_(0, inverse * self.shape[1] + colours,
                                   torch.ones_like(colours, dtype=self.values.dtype))
        merged = torch.unique(torch.cat([self.indices, rows]), sorted=True)
        values = torch.zeros((len(merged) + 1, self.shape[1]), dtype=self.values.dtype, device=self.values.device)
        values[torch.searchsorted(merged, self.indices)] = self.values[:-1]
        values[torch.searchsorted(merged, rows)] += updates
        self.indices, self.values = merged, values

    def to_sparse(self):
        nz = self.values[:-1].nonzero(as_tuple=False)
        indices = torch.stack([self.indices[nz[:, 0]], nz[:, 1]])
        return torch.sparse_coo_tensor(indices, self.values[nz[:, 0], nz[:, 1]], self.shape).coalesce()


def downsample_lab(lab, size):
    """Average actual contiguous pixel blocks of a square B,H,W,3 tensor."""
    b, h, w, channels = lab.shape
    if h != w or channels != 3 or h % size:
        raise ValueError('Expected square Lab images with a size divisible by the target')
    k = h // size
    return lab.reshape(b, size, k, size, k, 3).mean((2, 4))


def luminance_weights(palette, bias, temperature):
    """Bounded exponential tilt of palette lightness, applied before temperature.

    This changes sampling probabilities, never recolours finished pixels. Bias is
    a scalar selected against aggregate training counts, not a learned neuron.
    """
    exponent = (float(bias) * (palette[:, 0] - 50.0) / 20.0).clamp(-3, 3)
    return torch.exp(exponent * temperature)
