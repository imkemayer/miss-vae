import numpy as np


# Low rank matrix factorization
def gen_lrmf(n=1000, d=3, p=100, tau = 1, link = "linear",
             citcio = False, prop_miss = 0,
             seed=0, noise_sd = 1, sd = .1):

    # V is fixed throughout experiments for given n,p,d
    np.random.seed(0)
    V = np.random.randn(p,d) 

    np.random.seed(seed)
    Z = np.random.randn(n,d)
    
    X = Z.dot(V.transpose())
    assert X.shape == (n,p)

    X = X + noise_sd*np.random.randn(n,p) # add perturbation to observation matrix

    if not(citcio):
        # generate treatment assignment W
        ps, w = gen_treat(Z, link)

        # generate outcome
        y = gen_outcome(Z, w, tau, link, sd=sd)
    else:
        ps, w, y = citcio_treat_out(X, prop_miss, seed, link, tau, sd)

    # print(y.shape, Z.shape, w.shape)
    assert y.shape == (n,)
    assert w.shape == (n,)
    assert Z.shape == (n,d)

    return Z, X, w, y, ps

# Deep Latent Variable Model (here, we use an MLP)
def gen_dlvm(n=1000, d=3, p=100, tau = 1, link = "linear", 
             citcio = False, prop_miss = 0,
             seed=0,
             h = 5, sd = .1):

    # V, W, a, b, alpha, beta are fixed throughout experiments for given n,p,d,h
    np.random.seed(0)
    V = np.random.randn(p,h)
    W = np.random.uniform(0,1,h*d).reshape((h,d))
    a = np.random.uniform(0,1,h).reshape((h,1))
    b = np.random.randn(p,1)
    alpha = np.random.randn(h,1)
    beta = np.random.uniform(0,1,1)

    np.random.seed(seed)
    Z = np.random.randn(n,d)

    X = np.empty([n,p])
    for i in range(n):
        mu, Sigma = get_dlvm_params(Z[i,:].reshape(d,1), V, W, a, b, alpha, beta)
        X[i,:] = np.random.multivariate_normal(mu, Sigma, 1)

    assert X.shape == (n,p)

    if not(citcio):
        # generate treatment assignment W
        ps, w = gen_treat(Z, link)
        # generate outcome
        y = gen_outcome(Z, w, tau, link, sd=sd)
    else:
        ps, w, y = citcio_treat_out(X, prop_miss, seed, link, tau, sd)

    # print(y.shape, Z.shape, W.shape)
    assert y.shape == (n,)
    assert w.shape == (n,)
    assert Z.shape == (n,d)

    return Z, X, w, y, ps

# Compute expectation and covariance of conditional distribution X given Z
def get_dlvm_params(z, V, W, a, b, alpha, beta):
    
    # print(W.shape, z.shape, a.shape, z.shape)
    hu = (W.dot(z) + a).reshape(-1,1) # same shape of a (not h)
    # u = W.dot(z) + a
    mu = (V.dot(np.tanh(hu)) + b).reshape(-1,)
    sig = np.exp(alpha.transpose().dot(np.tanh(hu)) + beta)
    Sigma = sig*np.identity(mu.shape[0])
    
    return mu, Sigma

def citcio_treat_out(X, prop_miss, seed, link, tau, sd):
    from sklearn.experimental import enable_iterative_imputer
    from sklearn.impute import IterativeImputer

    X_miss = ampute(X, prop_miss = prop_miss, seed = seed)
    imp = IterativeImputer()
    X_imp = imp.fit_transform(X_miss)

    ps, w = gen_treat(X_imp, link = link)
    y = gen_outcome(X_imp, w, tau, link, sd)

    return ps, w, y

# Generate treatment assignment using confounders Z
def gen_treat(Z, link = "linear"):
    if link == "linear":
        ncolZ = Z.shape[1]
        beta = np.tile([0.6, -0.6], int(np.ceil(ncolZ/2.))) * 2
        beta = beta[:ncolZ]
        f_Z = Z.dot(beta)
        ps = 1/(1+np.exp(-f_Z))
        w = np.random.binomial(1, ps)
        balanced = np.mean(w) > 0.4 and np.mean(w) < 0.6

        # adjust the intercept term if necessary to ensure balanced treatment groups
        offsets = np.linspace(-5, 5, num=50)
        i, best_idx, min_diff = 0, 0, Z.shape[0]
        while i < len(offsets) and not balanced:
            ps = 1/(1+np.exp(-offsets[i] - f_Z))
            w = np.random.binomial(1, ps)
            balanced = np.mean(w) > 0.4 and np.mean(w) < 0.6
            diff = abs(np.mean(w) - np.mean(1-w))
            if diff < min_diff:
                best_idx, min_diff = i, diff
            i += 1
        if (i == len(offsets)):
            ps = 1/(1+np.exp(-offsets[best_idx]-f_Z))
            w = np.random.binomial(1, ps)
    elif link == "nonlinear":
        raise NotImplementedError("Nonlinear w~Z not defined yet.")
    else:
        raise ValueError("'link' should be choosed between linear and nonlinear model for w. got %s", link)
    return ps, w

# Generate outcomes using confounders Z, treatment assignment w and ATE tau
def gen_outcome(Z, w, tau, link = "linear", sd=10):
    if link == "linear":
        n = Z.shape[0]
        ncolZ = Z.shape[1]
        epsilon = sd*np.random.randn(n)
        beta = np.tile([-0.2, 0.155, 0.5, -1, 0.2], int(np.ceil(ncolZ/5.)))  
        beta = beta[:ncolZ]
        y = 0.5 + Z.dot(beta).reshape((-1)) + tau*w + epsilon
    elif link == "nonlinear":
        raise NotImplementedError("Nonlinear w~Z not defined yet.")
    else:
        raise ValueError("'link' should be choosed between linear and nonlinear model for y. got %s", link)
    return y

# Generate missing values in X such that, on average, X contains 100*prop_miss missing values
def ampute(X, prop_miss = 0.1, seed=0):
    np.random.seed(seed)
    # X_miss = np.copy(X)
    # mask = np.random.binomial(1,prop_miss, size=X.shape)
    # X_miss[mask] = np.nan
    n,p = X.shape
    X_miss = np.copy(X)
    X_miss_flat = X_miss.flatten()
    miss_pattern = np.random.choice(n*p, np.floor(n*p*prop_miss).astype(np.int), replace=False)
    X_miss_flat[miss_pattern] = np.nan 
    X_miss = X_miss_flat.reshape([n,p]) # in xmiss, the missing values are represented by nans
    # mask = np.isfinite(X_miss)
    return X_miss