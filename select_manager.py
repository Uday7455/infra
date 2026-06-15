"""
Data Manager definitions
"""
from typing import List, Optional, Union

from qali.intersight.gui.model_util import ContextManager, context_retry


class SelectManager(ContextManager):
    """
        Select Manager class definition

        Select Manager is responsible to find/retry select context interaction.

        The manager object is created when data_ctx is access from Intersight UI object.
    """

    CONTEXT_NAME = "select_context"

    def repr(self) -> str:
        """
            return representation string of select context

            :return: representation string of select context
        """
        if self.path_contexts is None:
            return str(("select", self.context))
        return str(("select", (self.context, self.path_contexts)))

    @context_retry(2)
    def select(self,
               value: Union[bool, str],
               timeout: Optional[int] = None,
               backward_compatible: bool = True,
               expected_value: dict = None,
               verify_selection: bool = True) -> None:
        """
            select value of the context 

            :param value: value to be selected
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param expected_value(dict): For Table Select Drawer If the selected row's value is from some other
              column then "Name" we can use this for validation purpose, whether we selected correct value or not.
              We need to pass dict as {"column":"expected_value"} and it will verify wether that column has that 
              expected value or not.
            :param verify_selection: If True, after attempting to select the value, a verification step will be 
              performed to ensure the element's 'checked' attribute reflects the intended value. If False, no such
              verification is performed.

            :return None
        """
        if not verify_selection:
            self.curr_context.select(value, timeout, backward_compatible, verify_selection)
        elif expected_value:
            self.curr_context.select(value, timeout, backward_compatible, expected_value)
        else:
            self.curr_context.select(value, timeout, backward_compatible)
        self.log("Select '{0}' with value '{1}'".format(self.context_name,
                                                        value))
        return self.curr_context.select_err_msg()

    @context_retry(1)
    def select_with_create(self, timeout: Optional[int] = None) -> None:
        """
            select by creating new value.
            For example, select policy reference by creating new policy first

            :param timeout: time to wait for the web element to be ready
            :return None
        """

        self.curr_context.select_with_create(timeout)
        self.log("Select '{0}' with create".format(self.context_name))

    @context_retry(2)
    def select_with_add(self,
                        values: Union[List[str], str],
                        timeout: Optional[int] = None,
                        backward_compatible: bool = True) -> None:
        """
            select by adding a new value.

            :param timeout: time to wait for the web element to be ready
            :return None
        """
        self.curr_context.select_with_add(values, timeout, backward_compatible)
        self.log("Select '{0}' with add".format(self.context_name))

    @context_retry(2)
    def clear(self,
              value: Union[str, None] = None,
              timeout: Optional[int] = None,
              backward_compatible: bool = True) -> None:
        """
            clear selected value.  If value is given, clear only if selected value equal to given value.

            :param value: If None, clear any value selected.  Otherwise, only clear matched value
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.


            :return None
        """
        self.curr_context.clear(value, timeout, backward_compatible)
        self.log("Clear '{0}' selection".format(self.context_name))

    @context_retry(1)
    def selected(self,
                 timeout: Optional[int] = None,
                 backward_compatible: bool = True) -> List[str]:
        """
            return selected choice

            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.

            :return selected choice
        """

        value = self.curr_context.selected(timeout, backward_compatible)
        self.log("'{0}' has selected value {1}".format(
            self.context_name,
            value))

        return value

    @context_retry(2)
    def choices(self,
                enabled: Union[bool, None] = None,
                timeout: Optional[int] = None,
                backward_compatible: bool = True,
                prefixes: Optional[List[str]] = None) -> List[str]:
        """
            return selection choices

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for the web element to be ready
            :param backward_compatible: backward compatibility should be consider or not.
            :param prefixes: Specify the list of prefixes level to view the choices.

            :return list of choices for selection
        """

        if prefixes:
            choices = self.curr_context.choices(
                enabled, timeout, backward_compatible, prefixes)
        else:
            choices = self.curr_context.choices(
                enabled, timeout, backward_compatible)
        choice_type = ""
        if enabled is not None:
            choice_type = 'enabled ' if enabled else 'disabled '

        self.log("'{0}' has {1}choices {2}".format(self.context_name,
                                                   choice_type,
                                                   choices))

        return choices

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

    @context_retry(2)
    def get_selector_cell_tooltip(self,
                                  column_value: str,
                                  column: str,
                                  timeout: Optional[int] = None) -> str:
        """
            Open the selector drawer, filter by column value, hover on the matching cell's column,
            and return tooltip data. Only supported for policy-manager selectors with table format
            (ucs-policy-manager-selector-table). Column value is unique per table; tables are
            searched in order (filter table 1, if not found filter table 2).

            :param column_value: value to filter by in the Name column (e.g. "my-policy" or "org-name/my-policy")
            :param column: column name (e.g., "Name", "Organization", "Description")
            :param timeout: time to wait for drawer and table to be ready
            :return: tooltip text for the cell (full content when truncated)
        """
        info = self.curr_context.get_selector_cell_tooltip(column_value, column, timeout)
        self.log("'{0}' read selector cell tooltip for value '{1}' column {2}: {3}".format(
            self.context_name, column_value, column, info))
        return info
