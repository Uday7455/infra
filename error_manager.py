"""
Error Manager definitions
"""
from typing import Optional
from qali.intersight.gui.model_util import context_retry
from qali.intersight.gui.model_util import ContextManager


class ErrorManager(ContextManager):
    """
        Error Manager class definition

        Error Manager is responsible to error context interaction.

        The manager object is created when error_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "error_context"

    def repr(self) -> str:
        """
            return representation string of error context

            :return: representation string of error context
        """
        if self.path_contexts is None:
            return str(("error", self.context))
        return str(("error", (self.context, self.path_contexts)))

    @context_retry(1)
    def text(self, timeout: Optional[int] = None) -> str:
        """
            read error text from the context

            :param timeout: time to wait for context to be ready
            :return: error in the context
        """
        data = self.curr_context.text(timeout=timeout)
        return data
