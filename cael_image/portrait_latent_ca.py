"""Integer-count factor-lattice CA; aggregate bins and joint category counts."""
import torch


def compile_latent_counts(z):
    """z: fitting rows x standardized appearance factors; keep aggregates only."""
    n, rank = z.shape
    if rank < 4 or rank % 4:
        raise ValueError('The factor lattice requires a rank divisible by four')
    edges = torch.tensor([-.75, -.25, .25, .75])
    bins = torch.bucketize(z.contiguous(), edges)
    marginal = torch.zeros(rank, 5, dtype=torch.int32)
    pair = torch.zeros(rank, 4, 6, 5, dtype=torch.int32)
    sums, squares = torch.zeros(rank, 5), torch.zeros(rank, 5)
    for cell in range(rank):
        labels = bins[:, cell]
        marginal[cell].index_add_(0, labels, torch.ones(n, dtype=torch.int32))
        sums[cell].index_add_(0, labels, z[:, cell])
        squares[cell].index_add_(0, labels, z[:, cell] ** 2)
        for direction, other in enumerate(neighbour_cells(cell, rank)):
            neighbour = torch.full((n,), 5, dtype=torch.long) if other is None else bins[:, other]
            pair[cell, direction].view(-1).index_add_(0, neighbour * 5 + labels, torch.ones(n, dtype=torch.int32))
    means = sums / marginal.clamp_min(1)
    variances = (squares / marginal.clamp_min(1) - means ** 2).clamp_min(.04)
    configurations, configuration_counts = torch.unique(bins, dim=0, return_counts=True)
    return dict(marginal=marginal, pairs=pair, means=means, variances=variances,
                joint_categories=configurations.to(torch.uint8), joint_counts=configuration_counts.to(torch.int32),
                fitting_count=n, categories=5, source_vectors_stored=False)


def neighbour_cells(cell, rank=8):
    row, col = divmod(cell, 4)
    return (cell - 4 if row else None, cell + 1 if col < 3 else None,
            cell + 4 if row < rank // 4 - 1 else None, cell - 1 if col else None)


def sample_latent_ca(statistics, count, generator, sweeps=12, joint_seed=False):
    rank = len(statistics['marginal'])
    prior = statistics['marginal'].float() + .5
    labels = torch.multinomial(prior, count, replacement=True, generator=generator).T.contiguous()
    if joint_seed and 'joint_categories' in statistics:
        chosen = torch.multinomial(statistics['joint_counts'].float(), count,
                                   replacement=count > len(statistics['joint_counts']), generator=generator)
        labels = statistics['joint_categories'][chosen].long().clone()
        # Stay near a learned joint configuration while local transitions mix it.
        seed_labels = labels.clone()
    for sweep in range(sweeps):
        for parity in (0, 1):
            previous = labels.clone()
            for cell in range(rank):
                row, col = divmod(cell, 4)
                if (row + col) % 2 != parity:
                    continue
                p = prior[cell].expand(count, -1).clone()
                if joint_seed and 'joint_categories' in statistics:
                    anchor = torch.full_like(p, .05)
                    anchor[torch.arange(count), seed_labels[:, cell]] = 1.
                    p *= anchor
                for direction, other in enumerate(neighbour_cells(cell, rank)):
                    value = torch.full((count,), 5, dtype=torch.long) if other is None else previous[:, other]
                    evidence = statistics['pairs'][cell, direction, value].float() + .5
                    conditional = evidence / evidence.sum(-1, keepdim=True)
                    base = prior[cell] / prior[cell].sum()
                    p *= (conditional / base).clamp(.2, 5.) ** .5
                labels[:, cell] = torch.multinomial(p / p.sum(-1, keepdim=True), 1, generator=generator).squeeze(1)
    cell = torch.arange(rank)[None].expand(count, -1)
    mean = statistics['means'][cell, labels]
    noise = torch.randn(count, rank, generator=generator) * statistics['variances'][cell, labels].sqrt() * .5
    return (mean + noise).clamp(-2, 2)
