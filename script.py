
import sys
import os
import libvirt
from typing import Callable, TypeAlias
from enum import Enum
from xml.etree import ElementTree as ET

libvirtURI: str = "qemu:///system"
connType: TypeAlias = libvirt.virConnect
domainType: TypeAlias = libvirt.virDomain
snapshotType: TypeAlias = libvirt.virDomainSnapshot

class Action(Enum):
	LIST	= 0
	CREATE	= 1
	REVERT	= 2
	DELETE	= 3
	EXIT	= 4

action2str: dict[Action, str] = {
	Action.LIST:	"List snapshots",
	Action.CREATE:	"Create snapshot",
	Action.REVERT:	"Revert snapshot",
	Action.DELETE:	"Delete snapshot",
	Action.EXIT:	"Exit",
}

def checkRoot():
	if os.geteuid() != 0:
		print("Warning: non-root user might not have access to the libvirt API", file=sys.stderr)

def checkDomains(conn: connType):
	if len(getDomains(conn)) < 1:
		print("Error: no domains found", file=sys.stderr)

def getDomains(conn: connType) -> list[domainType]:
	return conn.listAllDomains(0)

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
	if len(options) < 1:
		print("Error: no options available", file=sys.stderr)
		return 0
	for i, option in enumerate(options):
		print("\t[{:d}]: {:s}".format(i + 1, option))
	return (inputInt(start=1, end=len(options)) - 1)

def menuAction(conn: connType) -> Action:
	print()
	print("Select an action:")
	return Action(menu(list(action2str.values())))

def findRoot(snapshots: list[snapshotType]) -> snapshotType|None:
	children: set[libvirt.virDomainSnapshot] = set()
	for snapshot in snapshots:
		children.union(snapshot.listAllChildren())
	for snapshot in snapshots:
		if snapshot not in children:
			return snapshot
	return None

def actionList(domain: domainType):
	for (flags, typeStr) in [(libvirt.VIR_DOMAIN_SNAPSHOT_LIST_EXTERNAL, "External"), (libvirt.VIR_DOMAIN_SNAPSHOT_LIST_INTERNAL, "Internal")]:
		snapshots: list[snapshotType] = domain.listAllSnapshots(flags=flags)
		root: snapshotType|None = findRoot(snapshots)
		print()
		print("{:s}: ".format(typeStr))
		print(" Current |    Name    |   Parent   ")
		print("---------+------------+------------")
		for snapshot in snapshots:
			current: str = "*" if snapshot.isCurrent() else " "
			name: str = snapshot.getName()
			parent: str = snapshot.getParent().getName() if snapshot is not root else "    -     "
			print("    {:1s}    | {:10s} | {:10s} ".format(current, name, parent))

def diskSelection(domain: domainType) -> ET.Element:
	tree = ET.fromstring(domain.XMLDesc(0))
	blockDevices = []
	for target in tree.findall("devices/disk"):
		blockDevice: str = ""
		blockDevice += str(target.findall("source")[0].get("file")) + ", "
		blockDevice += str(target.findall("driver")[0].get("type")) + ", "
		blockDevice += str(target.findall("target")[0].get("dev"))
		blockDevices.append(blockDevice)
	diskIndex = menu(blockDevices)
	diskXml: ET.Element = tree.findall("devices/disk")[diskIndex]
	return diskXml

def actionCreate(domain: domainType):

	# root
	print()
	print("Select snapshot type: ")
	internal: bool = bool(menu(["External (recommended)", "Internal"]))
	xmlRoot = ET.Element("domainsnapshot")
	
	# name
	xmlName = ET.SubElement(xmlRoot, "name")
	print()
	while xmlName.text is None or len(xmlName.text) < 1:
		xmlName.text = input("Enter snapshot name: ")

	# desc
	print()
	descText = input("Enter snapshot description (optional): ")
	if len(descText) > 0:
		xmlDesc = ET.SubElement(xmlRoot, "description")
		xmlDesc.text = descText

	flags: int = 0
	if not internal:
		flags |= libvirt.VIR_DOMAIN_SNAPSHOT_CREATE_DISK_ONLY
		disk: ET.Element = diskSelection(domain)
		xmlDisks: ET.Element = ET.SubElement(xmlRoot, "disks")
		xmlDisk: ET.Element = ET.SubElement(xmlDisks, "disk", name=str(disk.findall("target")[0].get("dev")), snapshot="external")

	xmlStr: str = ET.tostring(xmlRoot).decode()
	domain.snapshotCreateXML(xmlStr, flags=flags)
	print("Successfully created snapshot \"{:s}\" for domain \"{:s}\"".format(xmlName.text, domain.name()))

def actionDelete(domain: domainType):
	snapshots: list[snapshotType] = domain.listAllSnapshots()
	print()
	print("Select snapshot to delete: ")
	snapshot: snapshotType = snapshots[menu([snapshot.getName() for snapshot in snapshots])]
	snapshot.delete()

def action2fun(conn: connType, action: Action) -> Callable[[domainType], None]:
	match action:
		case Action.LIST:
			return actionList
		case Action.CREATE:
			return actionCreate
		case Action.REVERT:
			return lambda x: None
		case Action.DELETE:
			return actionDelete
		case Action.EXIT:
			conn.close()
			exit(0)
			return lambda x: None

def menuDomain(conn: connType) -> domainType:
	domains: list[domainType] = getDomains(conn)
	print()
	print("Select a domain:")
	domainNames: list[str] = [domain.name() for domain in domains]
	domain: domainType = domains[menu(domainNames)]
	return domain

def main():
	checkRoot()
	conn: connType = libvirt.open(libvirtURI)
	checkDomains(conn)
	while True:
		domain: domainType = menuDomain(conn)
		action: Action = menuAction(conn)
		actionFun: Callable[[domainType], None] = action2fun(conn, action)
		actionFun(domain)

main()
