import csv
import sys
import logging
import os

from datetime import datetime

from .record import Record


DEFAULT_VERBOSE = False


class Validator:
    """Class for validating files of type {{ file_type }}."""

    def __init__(self, **kwargs):
        """Constructor for Validator"""
        self.config = kwargs.get("config", None)
        self.config_file = kwargs.get("config_file", None)
        self.logfile = kwargs.get("logfile", None)
        self.outdir = kwargs.get("outdir", None)
        self.verbose = kwargs.get("verbose", DEFAULT_VERBOSE)

        self.error_ctr = 0
        self.error_list = []

        logging.info(f"Instantiated Validator in file '{os.path.abspath(__file__)}'")

    def is_valid(self, infile: str) -> bool:
        """Determine whether the file is valid.

        Args:
            infile (str): the input file of type {{ file_type }} to be validated
        Returns:
            bool: True if valid, False if not valid
        """
        if not self._check_infile_status(infile=infile):
            logging.error(f"There is something wrong with the file '{infile}'. Please see the log file '{self.logfile}' for details.")
            sys.exit(1)

        record_ctr = 0
        header_to_position_lookup = {}

        with open(infile) as f:
            reader = csv.reader(f, delimiter='\t')
            row_ctr = 0
            for row in reader:
                row_ctr += 1
                if row_ctr == 1:
                    field_ctr = 0
                    for field in row:
                        header_to_position_lookup[field] = field_ctr
                        field_ctr += 1
                    logging.info(f"Processed the header of csv file '{infile}'")
                    continue
                else:
                    try:
                        record = Record(
                            {%- for field_name in field_lookup %}
                            {{ field_name }}=row[{{ field_lookup[field_name] }}],
                            {%- endfor %}
                        )
                    except Exception as e:
                        logging.error(f"Encountered some exception with row '{row_ctr}': {e}")
                        self.error_ctr += 1
                        self.error_list.append(e)

                    record_ctr += 1

            logging.info(f"Processed '{record_ctr}' records in data file '{infile}'")

        if self.error_ctr > 0:
            self._write_validation_report(infile)

    def _write_validation_report(self, infile: str) -> None:
        """Write the validation report file.

        Args:
            infile (str): the input file that was validated

        Returns:
            None
        """
        basename = os.path.basename(infile)

        outfile = os.path.join(self.outdir, f"{basename}.report.txt")

        with open(outfile, 'w') as of:
            of.write(f"## method-created: {os.path.abspath(__file__)}\n")
            of.write(f"## date-created: {str(datetime.today().strftime('%Y-%m-%d-%H%M%S'))}\n")
            of.write(f"## created-by: {os.environ.get('USER')}\n")
            of.write(f"## infile: {infile}\n")
            of.write(f"## logfile: {self.logfile}\n")

            if self.error_ctr > 0:
                of.write(f"Encountered the following '{self.error_ctr}' validation errors:\n")
                for error in self.error_list:
                    of.write(f"{error}\n")

        logging.info(f"Wrote file validation report file '{outfile}'")
        if self.verbose:
            print(f"Wrote file validation report file '{outfile}'")


    def _check_infile_status(self, infile: str = None, extension: str = None) -> bool:
        """Check if the file exists, if it is a regular file and whether it has content.

        Args:
            infile (str): the file to be checked

        Returns:
            is_valid (bool): True if all checks pass, False if not

        Raises:
            None
        """

        error_ctr = 0

        if infile is None or infile == '':
            logging.error(f"'{infile}' is not defined")
            error_ctr += 1
        else:
            if not os.path.exists(infile):
                error_ctr += 1
                logging.error(f"'{infile}' does not exist")
            else:
                if not os.path.isfile(infile):
                    error_ctr += 1
                    logging.error(f"'{infile}' is not a regular file")
                if os.stat(infile).st_size == 0:
                    logging.error(f"'{infile}' has no content")
                    error_ctr += 1
                if extension is not None and not infile.endswith(extension):
                    logging.error(f"'{infile}' does not have filename extension '{extension}'")
                    error_ctr += 1

        if error_ctr > 0:
            logging.error(f"Detected problems with input file '{infile}'")
            return False
        return True
