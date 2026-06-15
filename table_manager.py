"""
Table Manager definitions
"""
import pprint

# pylint: disable=too-many-public-methods
import re
from typing import Callable, List, Mapping, Optional, Union

from qali.intersight.gui.component_manager import ComponentManager
from qali.intersight.gui.iframe_manager import IframeManager
from qali.intersight.gui.model_util import ContextManager, PathContext, context_retry

RePattern = getattr(re, "Pattern")


class TableManager(ContextManager):
    """
        Table Manager class definition

        Table Manager is responsible to find/retry table context interaction.

        The manager object is created when table_ctx is access from Intersight UI object.
    """
    CONTEXT_NAME = "table_context"

    def __init__(self,
                 context: str,
                 path_contexts: Union[str, PathContext],
                 timeout: int,
                 component_manager: ComponentManager,
                 iframe_manager: IframeManager,
                 log: Callable,
                 screenshot: Callable,
                 page_errors: Callable) -> None:
        """
            init fucntion for table manager

            :param context: context for table action
            :param path_contexts: path context for table action.  This is mainly used as tie breaker
            :param timeout: time to wait for context to be ready
            :param component_manager:  component manager instance
            :param iframe_manager:  iframe manager instance
            :param log: logging function
            :param screenshot: screenshot function
            :param page_errors: page_errors function

            :return: None

        """
        super().__init__(context,
                         path_contexts,
                         timeout,
                         component_manager,
                         iframe_manager,
                         log,
                         screenshot,
                         page_errors)
        self._table_name = None

    def repr(self) -> str:
        """
            return representation string of table context

            :return: representation string of table context
        """
        if self.path_contexts is None:
            return str(("table", self.context))
        return str(("table", (self.context, self.path_contexts)))

    @property
    def table_name(self) -> str:
        """
            return name of the table.  Mainly for loggign purpose

            :return: table name
        """
        if self._table_name is None:
            self._table_name = "{0} table".format(
                self.context_name) if self.context else "table"
        return self._table_name

    @context_retry(1)
    def column_headers(self, timeout: Optional[int] = None) -> List[str]:
        """
            return column headers of the table

            :param timeout: time to wait for table to be loaded.

            :return: column headers of the table
        """

        col_headers = self.curr_context.column_headers(timeout=timeout)
        self.log("{0} has column header {1}".format(self.table_name,
                                                    col_headers))
        return col_headers

    @context_retry(3)
    def page_data(self,
                  page: Union[int, str, None] = None,
                  rows: Optional[List[int]] = None,
                  columns: Optional[List[str]] = None,
                  timeout: Optional[int] = None) -> Mapping[int, Mapping[str, str]]:
        """
            return data of given page of the table.  If page is None, then currrent page is returned.

            :param page: page number to use to get data from table.  If None, current page is used.
            :param rows: table rows to retrieve the data from.  If None, all rows will be retrieved.
            :param columns: table columns to retrieve the data from.  If None, all columns will be retrieved.
            :param timeout: time to wait for table to be loaded.

            :return: data of given page of the table
        """
        data = self.curr_context.page_data(page, rows, columns, timeout=timeout)
        self.log("'{0}' has page data {1}".format(self.table_name,
                                                  pprint.pformat(data)))
        return data

    @context_retry(2)
    def all_data(self,
                 columns: Optional[List[str]] = None,
                 timeout: Optional[int] = None) -> Mapping[int, Mapping[str, str]]:
        """
            return all page data of the table.  

            :param columns: table columns to retrieve the data from.  If None, all columns will be retrieved.
            :param timeout: time to wait for table to be loaded.            
            :return: data of given page of the table
        """

        data = self.curr_context.all_data(columns, timeout)
        self.log("'{0}' has all data {1}".format(self.table_name,
                                                 pprint.pformat(data)))
        return data

    @context_retry(1)
    def select_all(self, timeout: Optional[int] = None) -> None:
        """
            select all rows

            :param timeout: time to wait for table to be loaded.            
            :return: None

        """
        rtr = self.curr_context.select_all(timeout)
        self.log("Select all in {0}".format(self.table_name))
        return rtr

    @context_retry(2)
    def unselect_all(self, all_pages: bool = False, timeout: Optional[int] = None) -> None:
        """
            unselect all rows

            :param all_pages: whether to unselect all rowes in all page.
            :param timeout: time to wait for table to be loaded.            
            :return: None
        """

        rtr = self.curr_context.unselect_all(all_pages, timeout)
        self.log("Unselect all in {0}".format(self.table_name))
        return rtr

    @context_retry(2)
    def get_matched_row_indices(self,
                                row_info_list: List[Mapping[str, Union[str, RePattern]]],
                                timeout: Optional[int] = None) -> List[int]:
        """
            return list of row index that match criteria in row_info_list.
            The row_info_list is list of criteria.  As long as the row match one of criteria, it will
            be considered as match.  The criteria is a dictioanry with column name as key and desired matching value.
            The matching value can be either string or regular expression

            For example:

            with row_info_list as [{Name: "abc"}, {Name: re.compile("^xyz[0-9]$")}],
            It will return any row with Name = "abc" or Name starts with xyz following by 1 number. 

            :param row_info_list: list of matching criteria.     
            :param timeout: time to wait for table to be loaded.

            :return: list of matched row indices.
        """
        return self.curr_context.get_matched_row_indices(row_info_list, timeout=timeout)

    @context_retry(2)
    def select_rows(self,
                    row_indices: List[int],
                    timeout: Optional[int] = None) -> None:
        """
            select given row indices 

            :param row_indices: row indcies to select.
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        rtr = self.curr_context.select_rows(row_indices, timeout)
        self.log("Select row {0} in {1}".format(row_indices, self.table_name))
        return rtr

    @context_retry(1)
    def selected_rows(self,
                      timeout: Optional[int] = None) -> List[int]:
        """
            return rows selected in current table page

            :param timeout: time to wait for table to be loaded.

            :return: list of rows selected
        """

        rtr = self.curr_context.selected_rows(timeout)
        self.log(f"row {rtr} selected in {self.table_name}")
        return rtr

    @context_retry(1)
    def checkbox_disabled_selected_rows(self,
                                        timeout: Optional[int] = None) -> List[int]:
        """
         https://staging.starshipcloud.com/an/system/an/settings/resourceGroups/65eada3469726531019e1b39
            return rows with checkbox disabled and checked in current table page

        :param timeout: time to wait for table to be loaded.

        :return: list of rows disabled with checked
        """

        rtr = self.curr_context.checkbox_disabled_selected_rows(timeout)
        self.log(f"Checkbox with disabled selected row {rtr}  in {self.table_name}")
        return rtr

    @context_retry(1)
    def show_selected(self, timeout: int) -> bool:
        """
            show only selected rows

            :param timeout: time to wait for table to be loaded.            
            :return: True if show selected is clicked.  False if table already in show selected state
        """
        rtr = self.curr_context.show_selected(timeout)
        self.log("Clicked show selected on {0}".format(self.table_name))
        return rtr

    @context_retry(1)
    def show_all(self, timeout: int) -> bool:
        """
            show all rows

            :param timeout: time to wait for table to be loaded.
            :return: True if show all is clicked. False if table already in show all state
        """
        rtr = self.curr_context.show_all(timeout)
        self.log("Clicked show all on {0}".format(self.table_name))
        return rtr

    @context_retry(2)
    def unselect_rows(self,
                      row_indices: List[int],
                      timeout: Optional[int] = None) -> None:
        """
            unselect given row indices 

            :param row_indices: row indices to unselect.
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        rtr = self.curr_context.unselect_rows(row_indices, timeout)
        self.log("Unselect row {0} in {1}".format(
            row_indices, self.table_name))
        return rtr

    @context_retry(3)
    def sort_column(self,
                    column: str,
                    order: Optional[str],
                    timeout: Optional[int] = None) -> None:
        """
            sort give column with given order.  


            :param column: column name to be sorted.
            :param order: desired order for sorting.  Possible values are [None, "ascent", "descent", "asc", "desc"]
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        rtr = self.curr_context.sort_column(column, order, timeout)
        self.log("Sorted column {0} in {1} for {2}".format(
            column, order, self.table_name))
        return rtr

    @context_retry(2)
    def set_filter(self,
                   filter_str: str,
                   timeout: Optional[int] = None) -> None:
        """
            set table filter


            :param filter_str: filter string to set
            :param timeout: time to wait for table to be loaded.

            :return: None
        """

        rtr = self.curr_context.set_filter(filter_str, timeout)
        self.log("Set filter to '{0}' for {1}".format(
            filter_str, self.table_name))
        return rtr

    @context_retry(1)
    def clear_filter(self,
                     timeout: Optional[int] = None,
                     use_button: Optional[bool] = False) -> None:
        """
            clear table filter

            :param timeout: time to wait for table to be loaded.
            :param use_button: if True, use the 'X' button to clear filter.

            :return: None
        """
        rtr = self.curr_context.clear_filter(timeout, use_button)
        self.log("Clear filter for {0}".format(self.table_name))
        return rtr

    @context_retry(2)
    def get_filter(self,
                   timeout: Optional[int] = None,
                   dict_list: Optional[bool] = False) -> List[Union[str, dict]]:
        """
            get table filter current set to

            :param timeout: time to wait for table to be loaded.

            :return: filters set in the table
        """

        rtr = self.curr_context.get_filter(timeout, dict_list)
        self.log("filter is '{0}' for {1}".format(
            rtr, self.table_name))
        return rtr

    @context_retry(3)
    def click_cell(self,
                   row_index: int,
                   column: str,
                   timeout: Optional[int] = None) -> None:
        """
            click table cell for given row index and column 

            :param row_index: row index of the table cell
            :param column: column name of the table cell
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        rtr = self.curr_context.click_cell(row_index, column, timeout)
        self.log("Clicked call row {0} column {1} in {2}".format(
            row_index, column, self.table_name))
        return rtr

    @context_retry(2)
    def click_row_tree_toggle(self,
                              row_index: int,
                              timeout: Optional[int] = None,
                              expand: Optional[bool] = None) -> None:
        """
        Forward tree-row caret click to the current table context (same as DataTableContext).

        :param row_index: visible row index (first column tree caret).
        :param timeout: wait timeout for the table context.
        :param expand: optional; True expand only if collapsed, False collapse only if expanded,
            None toggle. Use keyword ``expand=`` so ``False`` is not mistaken for ``timeout``.
        :return: None.
        """
        rtr = self.curr_context.click_row_tree_toggle(row_index, timeout, expand)
        self.log("click_row_tree_toggle row {0} in {1} (expand={2})".format(
            row_index, self.table_name, expand))
        return rtr

    @context_retry(3)
    def hover_cell(self,
                   row_index: int,
                   column: str,
                   timeout: int) -> None:
        """
            Get hover data for a cell of a given row index and column 

            :param row_index: row index of the table cell
            :param column: column name of the table cell
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        rtr = self.curr_context.hover_cell(row_index, column, timeout)
        self.log("Hovered on row {0} column {1} in {2}".format(
            row_index, column, self.table_name))
        return rtr

    @context_retry(3)
    def action_on_row(self,
                      action: str,
                      row_index: int,
                      timeout: Optional[int] = None,
                      hover: Optional[bool] = False) -> None:
        """
            perform given action for given row of table

            :param action: action to perform on the table row.  Possible value can be found using 
                           self.action_on_row_choices method
            :param row_index: row index to perform the action on
            :param timeout: time to wait for table to be loaded.  
            :param hover: to hover over the action element.  

            :return: None   
        """
        rtr = self.curr_context.action_on_row(action, row_index, timeout, hover)
        self.log("Perform {0} on row {1} in {2}".format(
            action, row_index, self.table_name))
        return rtr

    @context_retry(3)
    def action_on_row_choices(self,
                              row_index: int,
                              enabled: Optional[bool] = None,
                              timeout: Optional[int] = None) -> List[str]:
        """
            return possible action choices for given row of table

            :param row_index: row index to get action choices
            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for table to be loaded.

            :return: list of possible action choices
        """
        rtr = self.curr_context.action_on_row_choices(
            row_index, enabled, timeout)
        self.log("Action choices on row {0} are {1} in {2}".format(
            row_index, rtr, self.table_name))
        return rtr

    @context_retry(3)
    def action_on_selected(self,
                           action: str,
                           use_footer: bool = False,
                           timeout: Optional[int] = None) -> None:
        """
            perform given action on selected row of the table

            :param action: action to perform on selected row.  Possible value can be found using 
                           self.action_on_selected_choices method
            :param use_footer: If True, trigger action from the bottom of the table.  Otherwise,
                               trigger from the top of the table.
            :param timeout: time to wait for table to be loaded.

            :return: None
        """
        rtr = self.curr_context.action_on_selected(action, use_footer, timeout)
        self.log("Perform {0} on selected rows in {1}".format(
            action, self.table_name))
        return rtr

    @context_retry(3)
    def action_on_selected_choices(self,
                                   use_footer: bool = False,
                                   enabled: Optional[bool] = None,
                                   timeout: Optional[int] = None) -> List[str]:
        """
            return action choices on selected row of the table

            :param use_footer: If True, trigger action from the bottom of the table.  Otherwise,
                               trigger from the top of the table.
            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for table to be loaded.
            :return: list of possible action choices
        """
        rtr = self.curr_context.action_on_selected_choices(
            use_footer, enabled, timeout)
        self.log("Action choices on selected rows are {0} for table {1}".format(
            rtr, self.table_name))
        return rtr

    @context_retry(1)
    def items_found(self, timeout: Optional[int] = None) -> int:
        """
            return items found for the table

            :param timeout: time to wait for table to be loaded.
            :return: items found for the table
        """
        rtr = self.curr_context.items_found(timeout)
        self.log("Item found in {0} is {1}".format(self.table_name, rtr))
        return rtr

    @context_retry(1)
    def items_selected(self, timeout: Optional[int] = None) -> Optional[int]:
        """
            return items selected for the table

            :param timeout: time to wait for table to be loaded.
            :return: items selected for the table
        """

        rtr = self.curr_context.items_selected(timeout)
        self.log(f"items selected in {self.table_name} is {rtr}")
        return rtr

    @context_retry(1)
    def per_page(self, timeout: Optional[int] = None) -> int:
        """
            return item per page for the table

            :param timeout: time to wait for table to be loaded.
            :return: item per page for the table
        """
        rtr = self.curr_context.per_page(timeout)
        self.log("Per page in {0} is {1}".format(self.table_name, rtr))
        return rtr

    @context_retry(2)
    def set_per_page(self, page_size: Union[str, int], timeout: Optional[int] = None) -> None:
        """
            set item per page for the table

            :param page_size: item per page to be set.
            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        rtr = self.curr_context.set_per_page(page_size, timeout)
        self.log("Set per page to {0} in {1}".format(
            page_size, self.table_name))
        return rtr

    @context_retry(2)
    def per_page_choices(self,
                         enabled: Optional[bool] = None,
                         timeout: Optional[int] = None) -> List[str]:
        """
            return item per page choices for the table

            :param enabled: if None, return all choices.  If True, return enabled choice only.  If False,
                            return disabled choice only.
            :param timeout: time to wait for table to be loaded.
            :return: item per page choices
        """
        rtr = self.curr_context.per_page_choices(enabled, timeout)
        self.log("Per page choices are {0} for {1}".format(
            rtr, self.table_name))
        return rtr

    @context_retry(1)
    def first_page(self, timeout: Optional[int] = None) -> None:
        """
            go to first page of the table

            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        rtr = self.curr_context.first_page(timeout)
        self.log("Clicked first page in {0}".format(self.table_name))
        return rtr

    @context_retry(1)
    def previous_page(self, timeout: Optional[int] = None) -> None:
        """
            go to previous page of the table

            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        rtr = self.curr_context.previous_page(timeout)
        self.log("Clicked previous page in {0}".format(self.table_name))
        return rtr

    @context_retry(1)
    def page_number(self, timeout: Optional[int] = None) -> int:
        """
            return current page number of the table

            :param timeout: time to wait for table to be loaded.
            :return: current page number of the table 
        """
        rtr = self.curr_context.page_number(timeout)
        self.log("Page number in {0} is {1}".format(self.table_name, rtr))
        return rtr

    @context_retry(2)
    def set_page_number(self,
                        page: Union[int, str],
                        timeout: Optional[int] = None) -> None:
        """
            set page number of the table


            :param page: page number to set to
            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        rtr = self.curr_context.set_page_number(page, timeout)
        self.log("Set Page number in {0} to {1}".format(self.table_name, page))
        return rtr

    @context_retry(1)
    def total_pages(self, timeout: Optional[int] = None) -> int:
        """
            return total pages of the table

            :param timeout: time to wait for table to be loaded.
            :return: total pages of the table
        """
        rtr = self.curr_context.total_pages(timeout)
        self.log("Total pages in {0} are {1}".format(self.table_name, rtr))
        return rtr

    @context_retry(1)
    def next_page(self, timeout: Optional[int] = None) -> None:
        """
            go to next page of the table

            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        rtr = self.curr_context.next_page(timeout)
        self.log("Clicked next page in {0}".format(self.table_name))
        return rtr

    @context_retry(1)
    def last_page(self, timeout: Optional[int] = None) -> None:
        """
            go to last page of the table

            :param timeout: time to wait for table to be loaded.
            :return: None
        """
        rtr = self.curr_context.last_page(timeout)
        self.log("Clicked last page in {0}".format(self.table_name))
        return rtr

    @context_retry(1)
    def get_search_attributes(self, timeout: Optional[int] = None) -> List[str]:
        """
            Click on filter and fetch all search attributes from dropdown
            :param timeout: time to wait for table to be loaded
            :return : List of seach attributes
        """
        rtr = self.curr_context.get_search_attributes(timeout)
        self.log("clicked on filter and fetching {0}".format(self.table_name))
        return rtr

    @context_retry(2)
    def add_custom_tab(self, custom_name=None, timeout: Optional[int] = None) -> None:
        """
        Add a custom tab for the table with a custom name

        :param custom_name: if custom_name is None ,default value will be saved else custom_name will be saved
        :param timeout: time to wait for table to be loaded.
        :return: None
        """
        rtr = self.curr_context.add_custom_tab(custom_name, timeout)
        self.log("Added a custom tab for the current table {0}".format(self.table_name))
        return rtr
