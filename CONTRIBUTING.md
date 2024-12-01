# Introduction

First off, thank you for considering contributing to `earthspy`! 😊

Following the guidelines presented here helps to communicate that you
respect the efforts the developers managing and developing this open
source project have put to foster community development. In return,
they should reciprocate that respect in addressing your issue,
assessing changes, and helping you finalize your pull requests. 🌻

Any kind of contribution is more than welcome. Improving
documentation, bug triaging, implementing new features or writing
tutorials are all examples of helpful contributions. 🚀

# Making a contribution

## Overview

 1. Fork `AdrienWehrle/earthspy` and clone your fork repository locally.
 2. Set up the development environment (section below).
 3. Create a branch for the new feature or bug fix.
 4. Make your changes, and add or modify related tests in
    [`tests/`](https://github.com/AdrienWehrle/earthspy/tree/main/tests).
 5. Commit, making sure to run pre-commit separately if not installed as git hook.
 6. Push to your fork.
 7. Open a pull request from GitHub to discuss and eventually merge.


## Step by step

### Setup

Clone the git repository and create a
[conda](https://docs.conda.io/projects/conda/en/latest/index.html) or
[mamba](https://mamba.readthedocs.io/en/latest/index.html)
environment. If you use mamba (mamba is great), just replace `conda`
for `mamba` below. Steps below are similar to those presented in the
[README](https://github.com/AdrienWehrle/earthspy/tree/main) except
[`dev-environment.yml`](https://github.com/AdrienWehrle/earthspy/blob/main/dev-environment.yml)
is used here instead of
[`environment.yml`](https://github.com/AdrienWehrle/earthspy/blob/main/dev-environment.yml)
as it contains necessary dependencies for continuous integration and
continuous development.

```bash

# clone repository
git clone git@github.com:AdrienWehrle/earthspy.git

# move into earthspy directory
cd earthspy

# create conda environment
conda env create -f dev-environment.yml

# activate conda environment
conda activate earthspy-dev

# install earthspy
pip install -e .
```

### Tests

If your PR targets the implementation of a new feature or the
improvement of existing ones, please add at least one test per feature
(in the associated
[`tests/test_earthspy.py`](https://github.com/AdrienWehrle/earthspy/blob/main/LICENSE)
file) and include them in your PR, using `pytest` (see existing tests
for examples).

To run the entire test suite, run pytest in the current directory:

```bash
pytest
```


### Formatting and linting

Before you make your commit, please install `pre-commit` (see
[pre-commit documentation](https://pre-commit.com/)), which will use
`.pre-commit-config.yaml` to verify spelling errors, import sorting,
type checking, formatting and linting.

You can then run `pre-commit` manually:

```bash
pre-commit run --all-files
```

In your PR, make sure to note if all `pre-commit` checks passed or
not. Other developers will gladly help you getting rid of remaining
red signs in your terminal if you feel stuck! 🌿

Optionally, `pre-commit` can also be installed as a git hook to
automatically ensure checks have to pass before committing.

Once all `pre-commit` checks have passed (or you need help),
please commit your changes with short and clear messages.


# Reporting a bug

## Security disclosures

If you find a security vulnerability, please do not open an
issue. Email adrien.wehrle@hotmail.fr instead.

In order to determine whether you are dealing with a security issue,
ask yourself these two questions:

- Can I access something that's not mine, or something I shouldn't
  have access to?
- Can I disable something for other people?

## How to file a bug report

When filing an issue at
[earthspy/issues](https://github.com/AdrienWehrle/earthspy/issues),
make sure to answer these five questions:

- Have you installed `earthspy` using
  [`environment.yml`](https://github.com/AdrienWehrle/earthspy/blob/main/LICENSE)?
  If not, what version of Python and dependencies are you using?
- What operating system and processor architecture are you using?
- What did you do?
- What did you expect to see?
- What did you see instead?


# Rights

The license (see
[`LICENSE`](https://github.com/AdrienWehrle/earthspy/blob/main/LICENSE))
applies to all contributions.

# Credits

Part of this document is based on [nayafia](https://github.com/nayafia)'s [CONTRIBUTING](https://github.com/nayafia) template and [geoutils CONTRIBUTING](https://github.com/GlacioHack/geoutils/blob/main/CONTRIBUTING.md).
