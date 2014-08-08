#!/usr/bin/env python

"""Module for building and running Fortran unit tests using a Python
interface to the FRUIT library:

http://sourceforge.net/projects/fortranxunit/

as a simple alternative to some of the original Ruby tools provided
with FRUIT.

Copyright 2014 University of Auckland.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

class test_subroutine(object):
    """Stores test subroutine data."""
    
    def __init__(self, name = "", description = ""):
        self.name = name
        self.description = description

class test_module(object):

    """Stores test module data."""

    def __init__(self, test_filename):
        self.test_filename = test_filename
        self.parse()

    def __repr__(self):
        return str([sub.name for sub in self.subroutines])

    def parse(self):
        """Parse module name and test cases."""
        f = open(self.test_filename)
        self.parse_test_module_name(f)
        self.parse_subroutines(f)        
        f.close()

    def parse_test_module_name(self, f):
        """Parses test module name from file f."""
        line = f.readline()
        while 'module' not in line.lower(): line = f.readline()
        imod = line.find('module')
        self.test_module_name = line[imod:].strip().split()[1]

    def subroutine_type(self, name):
        """Returns type of subroutine, 'setup' or 'teardown' if it has
        either of those names, otherwise None."""
        lowername = name.lower()
        if lowername == 'setup': subtype = 'setup'
        elif lowername == 'teardown': subtype = 'teardown'
        elif lowername.startswith('test_'): subtype = 'test'
        else: subtype = None
        return subtype

    def parse_subroutine(self, f, line):
        """Parses a single subroutine in a test module."""
        isub = line.lower().find('subroutine')
        pre = line[:isub]
        if '!' not in pre and 'end' not in pre.lower():
            subname = line[isub:].strip().split()[1]
            bracpos = subname.find('(')
            if bracpos >=0: subname = subname[:bracpos]
            subtype = self.subroutine_type(subname)
            if subtype == 'test':
                line = f.readline()
                while not line.strip(): line = f.readline()
                comment_pos = line.find('!')
                if comment_pos >=0: description = line[comment_pos+1:].strip()
                else: description = subname
                sub = test_subroutine(subname, description)
                self.subroutines.append(sub)
            else:
                if subtype == 'setup': self.setup = True
                elif subtype == 'teardown': self.teardown = True

    def parse_subroutines(self, f):
        """Parses subroutines in test module."""
        self.setup, self.teardown = False, False
        self.subroutines = []
        line = f.readline()
        while line:
            if 'subroutine' in line.lower(): self.parse_subroutine(f, line)
            line = f.readline()

class test_result(object):

    def __init__(self, success = 0, total = 0):
        self.success = success
        self.total = total

    def __repr__(self):
        return "%d / %d (%3.0f%%)" % (self.success, self.total, self.percent)

    def get_percent(self):
        """Returns percentage of successful results."""
        try:
            return float(self.success) / float(self.total) * 100.
        except ZeroDivisionError: return 0.0
    percent = property(get_percent)
        
class test_suite(object):

    """Class for suite of FRUIT tests"""

    def __init__(self, test_filenames):
        from os.path import splitext
        if isinstance(test_filenames, str):  test_filenames = [test_filenames]
        self.test_filenames = test_filenames
        self.test_modules = []
        self.driver = None
        self.exe = None
        self.asserts = test_result()
        self.cases = test_result()
        self.parse()

    def __repr__(self):
        return '\n'.join([mod.test_filename + ': ' + str(mod) for mod in self.test_modules])

    def get_num_test_modules(self):
        return len(self.test_modules)
    num_test_modules = property(get_num_test_modules)

    def get_setup(self):
        return any([mod.setup for mod in self.test_modules])
    setup = property(get_setup)

    def get_teardown(self):
        return any([mod.teardown for mod in self.test_modules])
    teardown = property(get_teardown)

    def parse(self):
        """Parses test F90 files containing test cases."""
        for test_filename in self.test_filenames:
            mod = test_module(test_filename)
            self.test_modules.append(mod)

    def parse_test_module_name(self, f):
        """Parses test module name from file f."""
        line = f.readline()
        while 'module' not in line.lower(): line = f.readline()
        imod = line.find('module')
        self.test_module_name = line[imod:].strip().split()[1]

    def get_driver_lines(self):
        """Creates lines for driver program to write to file."""

        lines = []
        lines.append('program tests')
        lines.append('')

        lines.append('  ! Driver program for FRUIT unit tests in:')
        for mod in self.test_modules:
            lines.append('  ! ' + mod.test_filename.strip())
        lines.append('')

        lines.append('  ! Generated by FRUITPy.')
        lines.append('')

        lines.append('  use fruit')
        for mod in self.test_modules:
            lines.append('  use ' + mod.test_module_name)
        lines.append('')

        lines.append('  call init_fruit')
        if self.setup: lines.append('  call setup')
        lines.append('')

        for mod in self.test_modules:
            if self.num_test_modules > 1:
                lines.append('  ! ' + mod.test_filename.strip() + ':')
            for sub in mod.subroutines:
                lines.append('  call run_test_case(' + 
                             sub.name + ',"' + sub.description + '")')
            lines.append('')

        if self.teardown: lines.append('  call teardown')
        lines.append('  call fruit_summary')
        lines.append('  call fruit_finalize')
        lines.append('')
        lines.append('end program tests')

        return lines

    driver_lines = property(get_driver_lines)

    def write(self, driver):
        """Writes driver program to file."""
        self.driver = driver
        f = open(self.driver, 'w')
        f.write('\n'.join(self.driver_lines))
        f.close()
        
    def build(self, build_command):
        """Compiles and links FRUIT driver program. Returns True if
        the build was successful."""
        from subprocess import call
        from os.path import isfile, splitext
        from os import remove
        from sys import platform
        self.exe, ext = splitext(self.driver)
        if platform == 'win32': self.exe += ".exe"
        if isfile(self.exe) : remove(self.exe)
        call(build_command, shell = True)
        return isfile(self.exe)

    def run(self):
        """Runs test suite, and returns True if all tests passed."""
        import os
        from os.path import splitext, isfile
        from subprocess import call
        run = self.exe
        if os.name == "posix": run = "./" + run
        basename, ext = splitext(self.driver)
        self.outputfile = basename + '.out'
        run += " > " + self.outputfile
        call(run, shell = True)
        self.parse_output_file()
        return self.success

    def parse_output_file(self):
        """Parses output file."""
        self.get_output_lines()
        self.get_success()
        self.get_messages()
        self.get_statistics()

    def get_output_lines(self):
        """Reads output file into output property."""
        from os.path import isfile
        if isfile(self.outputfile):
            self.output_lines = open(self.outputfile).readlines()
        else: self.output_lines = []

    def get_output(self):
        """Gets output from output_lines, in a form suitable for display."""
        return ''.join(self.output_lines)
    output = property(get_output)

    def get_success(self):
        """Determines whether all tests ran successfully, by parsing the output."""
        self.success = any(["SUCCESSFUL!" in line for line in self.output_lines])

    def get_messages(self):
        """Parses output failure messages."""
        self.messages = []
        if not self.success:
            for i, line in enumerate(self.output_lines):
                if "Failed assertion messages:" in line:
                    for j in xrange(i+1, len(self.output_lines)):
                        msg = self.output_lines[j]
                        if "end of failed assertion messages." in msg: break
                        else: self.messages.append(msg.strip())
                    break

    def parse_summary_line(self, line):
        """Parses a summary line containing statistics on successful and total
        numbers of asserts or cases."""
        items = line.split()
        slashpos = -(items[::-1].index('/') + 1) # last occurrence of /
        return int(items[slashpos - 1]), int(items[slashpos + 1])

    def get_statistics(self):
        """Parses output success / failure statistics."""
        for i, line in enumerate(self.output_lines):
            if "Successful asserts / total asserts" in line:
                self.asserts.success, self.asserts.total = \
                    self.parse_summary_line(line)
                self.cases.success, self.cases.total = \
                    self.parse_summary_line(self.output_lines[i + 1])

    def summary(self):
        """Prints a summary of the test results."""
        if self.success: print "All tests passed."
        else:
            print "Some tests failed:\n"
            print '\n'.join(self.messages)
            print 
        print "Hit rate:"
        print "  asserts: ", self.asserts
        print "  cases  : ", self.cases

    def build_run(self, driver, build_command = "make"):
        """Writes, builds and runs test suite. Returns True if the
        build and all tests were successful.  The 'driver' string
        parameter specifies the name of the driver program source file
        to be created. The 'build' string parameter specifies the
        command for building the test driver program."""
        if self.num_test_modules > 0:
            self.write(driver)
            if self.build(build_command): return self.run()
        return False
    
if __name__ == '__main__':
    from sys import argv
    filename = argv[1]
    driver = argv[2]
    build = argv[3]
    test_suite(filename).build_run(driver, build)