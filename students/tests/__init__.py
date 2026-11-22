"""Test suite for the students app.

Note: this dev machine runs Python 3.14 while Django 4.2 officially supports up
to 3.12. Django 4.2's test-only template instrumentation copies the template
context, and `copy(super())` inside `BaseContext.__copy__` raises AttributeError
on 3.14, which turns every template-rendering test into an error. The shim below
implements the same copy semantics without that call. On the deployment image
(Python 3.12) it behaves identically.
"""
from django.template.context import BaseContext


def _safe_base_context_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__ = self.__dict__.copy()
    duplicate.dicts = self.dicts[:]
    return duplicate


if not getattr(BaseContext, "__copy_shim__", False):
    BaseContext.__copy__ = _safe_base_context_copy
    BaseContext.__copy_shim__ = True
