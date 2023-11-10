# -*- coding: utf-8 -*-
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import csv
import re
import logging
import os
import sys


from typing import Any, Dict, List

DEFAULT_VERBOSE = False


class Manager:
    """Class for managing the creation of the validation modules."""

    def __init__(self, **kwargs):
        """Constructor for Manager."""
        self.config = kwargs.get("config", None)
        self.config_file = kwargs.get("config_file", None)
        self.file_type = kwargs.get("file_type", None)
        self.logfile = kwargs.get("logfile", None)
        self.outdir = kwargs.get("outdir", None)
        self.template_path = kwargs.get("template_path", None)
        self.verbose = kwargs.get("verbose", DEFAULT_VERBOSE)

        # Define a regular expression pattern to match special characters
        self.pattern = r"[^a-zA-Z0-9\s]"  # This pattern will keep alphanumeric characters and whitespace

        self.column_name_to_attribute_name_lookup = {}
        self.max_equality_values = self.config["max_equality_values"]

        self._init_templating_system()

        logging.info(
            f"Instantiated Manager in file '{os.path.abspath(__file__)}'"
        )

    def _init_templating_system(self) -> None:
        """Initialize the Jinja2 templating loader and environment."""
        # Specify the path to the templates directory
        template_path = self.template_path

        if not os.path.exists(template_path):
            logging.error(f"template path '{template_path}' does not exist")
            sys.exit(1)

        # Create a FileSystemLoader and pass the template path to it
        loader = FileSystemLoader(template_path)

        # Create a Jinja2 Environment using the loader
        self.env = Environment(loader=loader)

    def generate_validation_modules(self, infile: str) -> None:
        """Generate the validation modules for the specified file.

        Args:
            infile (str): the input tab-delimited or csv file
        Returns:
            None
        """
        logging.info(
            f"Will attempt to generate validation modules for input file '{infile}'"
        )
        extension = os.path.splitext(infile)[1]

        if extension == ".csv":
            self._generate_validation_modules_for_csv_file(infile)
        elif extension == ".tsv":
            self._generate_validation_modules_for_tsv_file(infile)
        else:
            logging.error(
                f"Support does not exist for files with extension '{extension}'"
            )
            sys.exit(1)

    def _generate_validation_modules_for_csv_file(self, infile: str) -> None:
        """Generate the validation modules for the specified .csv file.

        Args:
            infile (str): the input .csv file
        Returns:
            None
        """
        logging.error(
            f"NOT YET IMPLEMENTED - unable to process .csv file '{infile}'"
        )
        sys.exit(1)

    def _generate_validation_modules_for_tsv_file(self, infile: str) -> None:
        """Generate the validation modules for the specified .tsv file.

        Args:
            infile (str): the input .tsv file
        Returns:
            None
        """

        if not os.path.exists(infile):
            raise Exception(f"file '{infile}' does not exist")

        header_to_position_lookup = {}

        header_to_position_lookup = self._derive_column_headers_for_tsv_file(
            infile
        )

        # self._generate_validator_class(header_to_position_lookup, infile)

        self._process_columns_for_tsv_file(infile, header_to_position_lookup)

    def _generate_validator_class(
        self, header_to_position_lookup: Dict[str, int], infile: str
    ) -> None:
        """TODO."""
        # Specify the name of the template file
        template_name = "validator.py"

        # Create a dictionary with data to be passed to the template
        lookup = {}

        for column_name, column_position in header_to_position_lookup.items():
            attribute_name = self.column_name_to_attribute_name_lookup[
                column_name
            ]
            lookup[attribute_name] = column_position

        data = {"field_lookup": lookup, "file_type": self.file_type}

        output = self._generate_output_from_template(template_name, data)

        outfile = os.path.join(self.outdir, template_name)

        self._write_class_file_from_template(
            template_name, outfile, output, infile
        )

    def _process_columns_for_tsv_file(
        self, infile: str, header_to_position_lookup: Dict[str, int]
    ) -> None:
        """TBD."""
        lookup = {}
        enum_lookup = {}

        for column_name, column_position in header_to_position_lookup.items():
            attribute_name = self.column_name_to_attribute_name_lookup[
                column_name
            ]
            logging.info(
                f"Processing column name '{column_name}' (with attribute name '{attribute_name}') at column position '{column_position}'"
            )

            if attribute_name not in lookup:
                class_name = self._derive_class_name_for_column_name(
                    column_name
                )

                lookup[attribute_name] = {
                    "datatype": "str",
                    "column_name": column_name,
                    "column_position": column_position + 1,
                    "class_name": class_name,
                }

            uniq_val_lookup = {}
            uniq_val_ctr = 0
            uniq_val_list = []

            with open(infile) as f:
                reader = csv.reader(f, delimiter="\t")
                row_ctr = 0
                for row in reader:
                    row_ctr += 1
                    if row_ctr == 1:
                        continue
                    else:
                        if len(row) == 0:
                            # Blank line to be skipped?
                            continue
                        # print(f"{row=}")
                        val = row[column_position]
                        if val not in uniq_val_lookup:
                            uniq_val_lookup[val] = 0
                            uniq_val_list.append(val)
                            uniq_val_ctr += 1
                        uniq_val_lookup[val] += 1

            datatype = self._determine_datatype(uniq_val_list)

            if datatype == "different":
                lookup[attribute_name]["datatype"] = "str"
            else:
                lookup[attribute_name]["datatype"] = datatype

            if uniq_val_ctr <= self.max_equality_values:
                logging.info(
                    f"Will generate enum class for attribute '{attribute_name}' for column '{column_name}' because the max unique values is '{uniq_val_ctr}'"
                )
                class_name = lookup[attribute_name]["class_name"]
                self._load_enum_lookup(
                    uniq_val_lookup, enum_lookup, class_name
                )
                lookup[attribute_name]["uniq_values"] = []
                for uniq_val in uniq_val_lookup:
                    lookup[attribute_name]["uniq_values"].append(uniq_val)

            self._write_column_report_file(
                column_name,
                column_position,
                infile,
                uniq_val_ctr,
                uniq_val_lookup,
                row_ctr,
            )

        self._generate_record_class(lookup, enum_lookup, infile)

    def _load_enum_lookup(
        self, uniq_val_lookup, enum_lookup, class_name
    ) -> None:
        """Load values into the enum lookup for this class.

        Args:
            TODO
        """
        if class_name not in enum_lookup:
            enum_lookup[class_name] = {}

        for val in uniq_val_lookup:
            enum_name = self._derive_attribute_name(val)

            enum_name = enum_name.upper()

            if len(enum_name) == 1 or re.search(r"^\d", val):
                enum_name = f"{class_name.upper()}_{val.upper()}"

            logging.info(f"{enum_name=} {val=}")

            enum_lookup[class_name][enum_name] = val

    def _write_column_report_file(
        self,
        column_name,
        column_position,
        infile,
        uniq_val_ctr,
        uniq_val_lookup,
        row_ctr,
    ) -> None:
        """Write the report file for the column.

        Args:
            TODO
        Returns:
            None
        """
        outfile = self._derive_column_outfile(column_name, column_position)

        total_row_count = row_ctr - 1

        with open(outfile, "w") as of:
            of.write(f"## method-created: {os.path.abspath(__file__)}\n")
            of.write(
                f"## date-created: {str(datetime.today().strftime('%Y-%m-%d-%H%M%S'))}\n"
            )
            of.write(f"## created-by: {os.environ.get('USER')}\n")
            of.write(f"## infile: {infile}\n")
            of.write(f"## logfile: {self.logfile}\n")

            of.write(f"Column name: '{column_name}'\n")
            of.write(f"Column position: '{column_position}'\n")
            of.write(f"Number of data rows: '{total_row_count}'\n")
            of.write(f"Here are the unique '{uniq_val_ctr}' values:\n")

            for val, count in uniq_val_lookup.items():
                percent = count / total_row_count * 100
                of.write(
                    f"value: '{val}'; count: {count}; percentage: {percent}\n"
                )

        logging.info(f"Wrote column report file '{outfile}'")
        if self.verbose:
            print(f"Wrote column report file '{outfile}'")

    def _derive_column_outfile(
        self, column_name: str, column_position: int
    ) -> str:
        """Derive the output file for the column-specific values.

        Args:
            column_name (str): the column name
        Returns:
            str: the output file
        """
        basename = (
            column_name.replace(" ", "")
            .replace("*", "")
            .replace("\\", "")
            .replace("/", "_")
            .replace("|", "_")
            .replace("(", "_")
            .replace(")", "_")
        )
        outfile = os.path.join(
            self.outdir, f"{column_position}_{basename}.tsv"
        )
        return outfile

    def _derive_column_headers_for_tsv_file(
        self, infile: str
    ) -> Dict[str, int]:
        """Derive the column headers for the input .tsv file.

        Args:
            infile (str): the file to be parsed
        Returns:
            dict: column header is the key and column number is the value
        """
        lookup = {}
        column_ctr = 0
        column_name_to_attribute_name_lookup = {}
        with open(infile) as f:
            reader = csv.reader(f, delimiter="\t")
            row_ctr = 0
            for row in reader:
                row_ctr += 1
                if row_ctr == 1:
                    for field in row:
                        lookup[field] = column_ctr
                        attribute_name = self._derive_attribute_name(field)
                        column_name_to_attribute_name_lookup[
                            field
                        ] = attribute_name
                        column_ctr += 1
                    logging.info(
                        f"Processed the header of .tsv file '{infile}'"
                    )
                    break
        logging.info(f"Found '{column_ctr}' columns in file '{infile}'")
        self.column_name_to_attribute_name_lookup = (
            column_name_to_attribute_name_lookup
        )
        return lookup

    def _derive_attribute_name(self, column_name: str) -> str:
        """Derive the attribute name for the column name.

        This will remove special characters and spaces and lowercase the string.
        Args:
            column_name (str): the column name
        Returns:
            str: the attribute name
        """
        # Use re.sub to replace all matches with an empty string
        attribute_name = re.sub(self.pattern, "", column_name)
        attribute_name = attribute_name.lower().replace(" ", "")
        return attribute_name

    def _snake_to_upper_camel(self, class_name: str):
        words = class_name.split("_")
        camel_case_words = [word.capitalize() for word in words]
        return "".join(camel_case_words)

    def _derive_class_name_for_column_name(self, column_name: str) -> str:
        """Derive the class name for the column name.

        This will remove special characters and spaces.
        Args:
            column_name (str): the column name
        Returns:
            str: the class name
        """
        class_name = (
            column_name.replace(" ", "_")
            .replace("*", "")
            .replace("#", "")
            .replace("\\", "")
            .replace("/", "_")
            .replace("|", "_")
            .replace("(", "_")
            .replace(")", "_")
        )

        return self._snake_to_upper_camel(class_name)

    def _generate_record_class(
        self,
        lookup: Dict[str, Dict[str, str]],
        enum_lookup: Dict[str, Dict[str, str]],
        infile: str,
    ) -> None:
        """TODO."""
        # Specify the name of the template file
        template_name = "record.py"

        # Create a dictionary with data to be passed to the template
        data = {
            "lookup": lookup,
            "file_type": self.file_type,
            "enum_lookup": enum_lookup,
        }

        output = self._generate_output_from_template(template_name, data)

        outfile = os.path.join(self.outdir, template_name)

        self._write_class_file_from_template(
            template_name, outfile, output, infile
        )

    def _generate_output_from_template(
        self, template_name: str, data: Dict[str, Dict]
    ) -> str:
        """TODO."""
        # Load the template
        template = self.env.get_template(template_name)

        # Render the template with the data
        output = template.render(data)

        return output

    def _write_class_file_from_template(
        self, template_name: str, outfile: str, output: str, infile: str
    ) -> None:
        with open(outfile, "w") as of:
            of.write(f'""" method-created: {os.path.abspath(__file__)}\n')
            of.write(
                f"date-created: {str(datetime.today().strftime('%Y-%m-%d-%H%M%S'))}\n"
            )
            of.write(f"created-by: {os.environ.get('USER')}\n")
            of.write(f"infile: {infile}\n")
            of.write(f'logfile: {self.logfile}"""\n')

            of.write(f"{output}\n")

        logging.info(f"Wrote {template_name} file '{outfile}'")
        if self.verbose:
            print(f"Wrote {template_name} file '{outfile}'")

    def _determine_datatype(self, values: List[Any]) -> str:
        # Check if the array is not empty
        if not values:
            logging.error("values array is empty")
            sys.exit(1)

        first_value = values[0]
        first_datatype = None
        first_datatype_clean = None

        if self._is_convertible_to_int(first_value):
            first_value = int(first_value)
            first_datatype = "int"
            first_datatype_clean = "int"
        elif self._is_convertible_to_float(first_value):
            first_value = float(first_value)
            first_datatype = "float"
            first_datatype_clean = "float"
        else:
            # Get the datatype of the first element
            first_datatype = type(first_value)
            first_datatype_clean = str(type(values[0])).split("'")[1]

        different = True

        # Iterate through the array starting from the second element
        for value in values[1:]:
            current_datatype = None
            # Check if the datatype of the current element matches the first datatype
            if self._is_convertible_to_int(value):
                value = int(value)
                if first_datatype == "int":
                    continue
            elif self._is_convertible_to_float(value):
                value = float(value)
                if first_datatype == "float":
                    continue

            if type(value) != first_datatype:
                logging.info(
                    f"values does not have a consistent datatype. Expected {first_datatype}, but found {type(value)}."
                )
                return "different"

        # If the loop completes without returning, all elements have the same datatype
        logging.info(
            f"All elements in the values array have the datatype: {first_datatype}"
        )
        return first_datatype_clean

    def _is_convertible_to_int(self, value):
        try:
            # Try converting the string to an integer
            int_value = int(value)
            logging.info(
                f"{value} can be safely converted into an integer value"
            )
            return True
        except ValueError:
            # Conversion failed
            logging.info(
                f"{value} cannot be safely converted into an integer value"
            )
            return False

    def _is_convertible_to_float(self, value):
        try:
            # Try converting the string to a float
            float_value = float(value)
            logging.info(
                f"{value} can be safely converted into an float value"
            )
            return True
        except ValueError:
            # Conversion failed
            logging.info(
                f"{value} cannot be safely converted into an float value"
            )
            return False
