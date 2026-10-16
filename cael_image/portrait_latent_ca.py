"""Integer count CA over eight appearance-factor categories; no source vectors."""
import torch


def compile_latent_counts(z):
    """z: fitting rows x standardized appearance factors; keep aggregates only."""
    n, rank = z.shape
    if rank != 8:
        raise ValueError('This experimental latent CA uses a 2x4 factor lattice')
    edges = torch.tensor([-.75, -.25, .25, .75])
    bins = torch.bucketize(z.contiguous(), edges)
    marginal = torch.zeros(8, 5, dtype=torch.int32)
    pair = torch.zeros(8, 4, 6, 5, dtype=torch.int32)
    sums, squares = torch.zeros(8, 5), torch.zeros(8, 5)
    for cell in range(8):
        labels = bins[:, cell]
        marginal[cell].index_add_(0, labels, torch.ones(n, dtype=torch.int32))
        sums[cell].index_add_(0, labels, z[:, cell])
        squares[cell].index_add_(0, labels, z[:, cell] ** 2)
        for direction, other in enumerate(neighbour_cells(cell)):
            neighbour = torch.full((n,), 5, dtype=torch.long) if other is None else bins[:, other]
            pair[cell, direction].view(-1).index_add_(0, neighbour * 5 + labels, torch.ones(n, dtype=torch.int32))
    means = sums / marginal.clamp_min(1)
    variances = (squares / marginal.clamp_min(1) - means ** 2).clamp_min(.04)
    return dict(marginal=marginal, pairs=pair, means=means, variances=variances,
                fitting_count=n, categories=5, source_vectors_stored=False)


def neighbour_cells(cell):
    row, col = divmod(cell, 4)
    return (cell - 4 if row else None, cell + 1 if col < 3 else None,
            cell + 4 if row == 0 else None, cell - 1 if col else None)


def sample_latent_ca(statistics, count, generator, sweeps=12):
    prior = statistics['marginal'].float() + .5
    labels = torch.multinomial(prior, count, replacement=True, generator=generator).T.contiguous()
    for sweep in range(sweeps):
        for parity in (0, 1):
            previous = labels.clone()
            for cell in range(8):
                row, col = divmod(cell, 4)
                if (row + col) % 2 != parity:
                    continue
                p = prior[cell].expand(count, -1).clone()
                for direction, other in enumerate(neighbour_cells(cell)):
                    value = torch.full((count,), 5, dtype=torch.long) if other is None else previous[:, other]
                    evidence = statistics['pairs'][cell, direction, value].float() + .5
                    conditional = evidence / evidence.sum(-1, keepdim=True)
                    base = prior[cell] / prior[cell].sum()
                    p *= (conditional / base).clamp(.2, 5.) ** .5
                labels[:, cell] = torch.multinomial(p / p.sum(-1, keepdim=True), 1, generator=generator).squeeze(1)
    cell = torch.arange(8)[None].expand(count, -1)
    mean = statistics['means'][cell, labels]
    noise = torch.randn(count, 8, generator=generator) * statistics['variances'][cell, labels].sqrt() * .5
    return (mean + noise).clamp(-2, 2)
