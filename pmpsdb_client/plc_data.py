"""
Get file info from, upload files to, and download files from the PLCs.

This calls methods from ssh_data and ftp_data as appropriate.
When the system is configured correctly, exactly one of these submodules
should work for getting data from the PLC.
"""
