"""
Input Manager definitions
"""
from typing import Union, Optional, List, Any
from qali.intersight.gui.model_util import context_retry
from qali.intersight.gui.model_util import ContextManager


class InputManager(ContextManager):
    """
        Input Manager class definition

        Input Manager is responsible to find/retry input context interaction.

        The manager object is created when input_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "input_context"

    def repr(self) -> str:
        """
            return representation string of input context

            :return: representation string of input context
        """
        if self.path_contexts is None:
            return str(("input", self.context))
        return str(("input", (self.context, self.path_contexts)))

    @context_retry(2)
    def input(self,
              value: Union[str, int, List[str]],
              timeout: Optional[int] = None,
              verify_value: Optional[Any] = None) -> str:
        """
            input value to the context.  return input error if any

            :param value: value to input
            :param timeout: time to wait for context to be ready
            :param verify_value: compare the set value with this value \
                to verify if a value has been set correctly in the UI
            :return: return "" if no input error.  Otherwise, input error string is returned
        """
        kwargs = {}
        if verify_value is not None:
            kwargs['verify_value'] = verify_value
        self.curr_context.input(value, timeout, **kwargs)
        if self.mask_pattern.match(self.context_name):
            self.log("Input '{0}' in '{1}'".format("******",
                                                   self.context_name))
        else:
            self.log("Input '{0}' in '{1}'".format(value,
                                                   self.context_name))

        return self.curr_context.input_err_msg()

    @context_retry(1)
    def value(self, timeout: Optional[int] = None) -> Union[str, List[str]]:
        """
            return input value in the context

            :param timeout: time to wait for context to be ready
            :return: input value in the context
        """

        value = self.curr_context.value(timeout)
        self.log("Read '{0}' with value {1}".format(
            self.context_name,
            value))
        return value

    @context_retry(1)
    def error(self, timeout: Optional[int] = None) -> str:
        """
            return input value in the context

            :param timeout: time to wait for context to be ready
            :return: input value in the context
        """

        err = self.curr_context.input_err_msg()
        self.log("Read '{0}' with error {1}".format(
            self.context_name,
            err))
        return err

    @context_retry(1)
    def is_enabled(self, timeout: Optional[int] = None) -> bool:
        """
            return if the field is enabled
            :param timeout: time to wait for context to be ready
            :return: True if the field is editable
                    False if the field is disabled
        """
        state = self.curr_context.is_enabled(timeout)
        self.log("'{0}' enable state is {1}".format(self.context_name, state))
        return state

    @context_retry(1)
    def get_tooltip(self, timeout: Optional[int] = None) -> str:
        """
            return tooltip data if present
            :param timeout: time to wait for context to be ready
            :return: return tooltip data if present
        """
        info = self.curr_context.get_tooltip(timeout)
        self.log("'{0}' read tooltip info {1}".format(self.context_name, info))
        return info
