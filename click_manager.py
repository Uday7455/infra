"""
Click Manager definitions
"""
from typing import Optional
from qali.intersight.gui.model_util import context_retry
from qali.intersight.gui.model_util import ContextManager


class ClickManager(ContextManager):
    """
        Click Manager class definition

        Click Manager is responsible to find/retry click context interaction.

        The manager object is created when click_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "click_context"

    def repr(self) -> str:
        """
            return representation string of click context

            :return: representation string of click context
        """
        if self.path_contexts is None:
            return str(("click", self.context))
        return str(("click", (self.context, self.path_contexts)))

    @context_retry(1)
    def click(self, timeout: Optional[int] = None) -> None:
        """
            perform click on the context

            :param timeout: time to wait for context to be ready
            :return: None
        """
        self.curr_context.click(timeout)
        self.log("clicked '{0}'".format(self.context_name))

    @context_retry(1)
    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return click context whether is enable or not.

            :param timeout: time to wait for context to be ready
            :return: True if click context is enable
        """
        rtr = self.curr_context.is_enabled(timeout)
        self.log("'{0}' enable state is {1}".format(self.context_name, rtr))
        return rtr

    @context_retry(1, ignore_error=True, default_timeout=2)
    def click_if_exist(self, timeout: int = 2) -> None:
        """
            perform click on the context if exist.

            :param timeout: time to wait to check if context exist and clickable
            :return: None
        """
        try:
            self.curr_context.click(timeout)
            self.log("clicked '{0}'".format(self.context_name))
        except Exception:
            pass

    @context_retry(1)
    def link(self, timeout: Optional[int] = None) -> str:
        """
            return click context whether is enable or not.

            :param timeout: time to wait for context to be ready
            :return: True if click context is enable
        """
        rtr = self.curr_context.link(timeout)
        self.log("'{0}' link is {1}".format(self.context_name, rtr))
        return rtr
