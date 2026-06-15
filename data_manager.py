"""
Data Manager definitions
"""
from typing import Optional, Union, Mapping
import pprint
from qali.intersight.gui.model_util import context_retry
from qali.intersight.gui.model_util import ContextManager


class DataManager(ContextManager):
    """
        Data Manager class definition

        Data Manager is responsible to find/retry data context interaction.

        The manager object is created when data_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "data_context"

    def repr(self) -> str:
        """
            return representation string of data context

            :return: representation string of data context
        """
        if self.path_contexts is None:
            return str(("data", self.context))
        return str(("data", (self.context, self.path_contexts)))

    @context_retry(1)
    def values(self, timeout: Optional[int] = None) -> Union[str, Mapping[str, str]]:
        """
            read data from the context

            :param timeout: time to wait for context to be ready
            :return: data in the context
        """

        data = self.curr_context.values(timeout=timeout)
        self.log("Read '{0}' with value {1}".format(self.context_name,
                                                    pprint.pformat(data)))
        return data

    @context_retry(1)
    def scroll_to_bottom(self, timeout: Optional[int] = None) -> None:
        """
        scroll to bottom of the data element

        :param timeout: time to wait for the web element to be ready
        :return: None
        """
        self.curr_context.scroll_to_bottom(timeout=timeout)
        self.log("Scroll to bottom of '{0}'".format(self.context_name))

    @context_retry(1)
    def tooltip_choices(self,
                        timeout: Optional[int] = None) -> list:
        """
            return tooltip choices
            :param timeout: time to wait for context to be ready
            :return: return tooltip choices
        """
        info = self.curr_context.tooltip_choices(timeout)
        return info

    @context_retry(2)
    def get_choice_tooltip(self, value: str,
                           timeout: Optional[int] = None,
                           backward_compatible: Optional[bool] = True) -> str:
        """
            return tooltip data of a choice if present
            :param value: choice whose tooltip info needs to be returned
            :param timeout: time to wait for context to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :return: return tooltip data of a choice if present
        """
        info = self.curr_context.get_choice_tooltip(value, timeout, backward_compatible)
        self.log("'{0}' read tooltip info {1}".format(self.context_name, info))
        return info
