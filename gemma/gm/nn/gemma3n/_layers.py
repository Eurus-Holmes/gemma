# Copyright 2025 DeepMind Technologies Limited.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Base layers."""

from flax import linen as nn
import jax
import jax.numpy as jnp


class Einsum(nn.Module):
  """Einsum is a convenience module for parameterized tensor multiplication."""

  shape: tuple[int, ...]
  weight_name: str = 'w'
  initializer: nn.initializers.Initializer = nn.initializers.normal()
  dtype: jnp.dtype | None = None
  w_scale: float | None = None

  @nn.compact
  def __call__(self, eqn: str, x: jax.Array) -> jax.Array:
    w = self.param(
        self.weight_name,
        self.initializer,
        self.shape,
        self.dtype if self.dtype is not None else None,
    )
    if self.w_scale:
      w *= self.w_scale
    return jnp.einsum(eqn, x, w)


def reduce_precision(x: jax.Array) -> jax.Array:
  """Helper function to reduce the precision of a tensor."""
  finfo = jnp.finfo(x.dtype)  # jnp important!
  return jax.lax.reduce_precision(x, finfo.nexp, finfo.nmant)


class RMSNorm(nn.Module):
  """RMSNorm layer."""

  with_scale: bool = True
  scale_init: nn.initializers.Initializer = nn.initializers.zeros_init()
  scale_plus_one: bool = True
  guard_against_excess_precision: bool = False

  @nn.compact
  def __call__(self, x):
    if self.guard_against_excess_precision:
      x = reduce_precision(x)

    var = jnp.mean(jnp.square(x), axis=-1, keepdims=True)

    # Jax.lax.rsqrt is used because it returns different floats than
    # jnp.reciprocal(jnp.sqrt(var + 1e-06))
    normed_inputs = x * jax.lax.rsqrt(var + 1e-06)

    if self.with_scale:
      scale = self.param('scale', self.scale_init, (x.shape[-1]))
      # normed_inputs is a rank-K tensor, K > 1 (K is typically 2 or 3). scale
      # is a rank-1 tensor. To avoid implicit rank-promotion, reshape scale to
      # a (1, ..., 1, D) tensor, so the rank of scale matches normed_inputs.
      scale = jnp.expand_dims(scale, axis=range(len(x.shape) - 1))
      normed_inputs = normed_inputs * (
          1. + scale if self.scale_plus_one else scale)
    return normed_inputs
