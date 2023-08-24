
import sys
import os
import libvirt
from typing import TypeAlias

libvirtURI: str = "qemu:///system"
connType: TypeAlias = libvirt.virConnect

def checkRoot():
	if os.geteuid() != 0:
		print("Warning: non-root user might not have access to the libvirt API", file=sys.stderr)

def inputInt(start: int, end: int) -> int:
	while True:
		strInput: str = input("Enter number in range [{:d}-{:d}]: ".format(start, end))
		try:
			intInput: int = int(strInput)
			if start <= intInput <= end:
				return intInput
			else:
				print("Entered number is not in range", file=sys.stderr)
		except ValueError:
			print("Input is not an integer", file=sys.stderr)

def menu(options: list[str]) -> int:
	if len(options) < 2:
		return 0
	print()
	for i, option in enumerate(options):
		print("\t[{:d}]: \"{:s}\"".format(i + 1, option))
	return inputInt(start=1, end=len(options))

def main():
	checkRoot()
	conn: connType = libvirt.open(libvirtURI)
	conn.close()

main()
