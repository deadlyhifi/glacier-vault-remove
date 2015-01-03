#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
import time
import os.path
import logging
import boto.glacier
from socket import gethostbyname, gaierror

# Default logging config
logging.basicConfig(format='%(levelname)s : %(asctime)s – %(message)s', level=logging.INFO, datefmt='%H:%M:%S')

# Get arguments
if len(sys.argv) >= 3:
	regionName = sys.argv[1]
	vaultName = sys.argv[2]
else:
	# If there are missing arguments, display usage example and exit
	logging.error('Usage: %s REGION_NAME VAULT_NAME', sys.argv[0])
	sys.exit(1)

# Get custom logging level
if len(sys.argv) == 4 and sys.argv[3] == 'DEBUG':
	logging.info('Logging level set to DEBUG.')
	logging.basicConfig(level=logging.DEBUG)

# Load credentials
f = open('credentials.json', 'r')
config = json.loads(f.read())
f.close()

try:
	logging.info('Connecting to Amazon Glacier…')
	glacier = boto.glacier.connect_to_region(regionName, aws_access_key_id=config['AWSAccessKeyId'], aws_secret_access_key=config['AWSSecretKey'])
except:
	logging.error(sys.exc_info()[0])
	sys.exit(1)

try:
	logging.info('Getting selected vault…')
	vault = glacier.get_vault(vaultName)
except:
	logging.error(sys.exc_info()[0])
	sys.exit(1)

logging.info('Getting jobs list…')
jobList = vault.list_jobs()
jobID = ''

# Check if a job already exists
for job in jobList:
	if job.action == 'InventoryRetrieval':
		logging.info('Found existing inventory retrieval job…')
		jobID = job.id

if jobID == '':
	logging.info('No existing job found, initiate inventory retrieval…')
	try:
		jobID = vault.retrieve_inventory(description='Python Amazon Glacier Removal Tool')
	except Exception, e:
		logging.error(e)
		sys.exit(1)

logging.debug('Job ID : %s', jobID)

# Get job status
job = vault.get_job(jobID)

while job.status_code == 'InProgress':
	logging.info('Inventory not ready, sleep for 30 mins…')

	time.sleep(60*30)

	job = vault.get_job(jobID)

if job.status_code == 'Succeeded':
	logging.info('Inventory retrieved, parsing data…')
	inventory = json.loads(job.get_output().read())

	logging.info('Removing archives… please be patient, this may take some time…');
	for archive in inventory['ArchiveList']:
		if archive['ArchiveId'] != '':
			logging.debug('Remove archive ID : %s', archive['ArchiveId'].encode("utf-8"))
			try:
				vault.delete_archive(archive['ArchiveId'])
			except Exception, e:
				logging.error(e)

				logging.info('Sleep 2 mins before retrying…')
				time.sleep(60*2)

				logging.info('Retry to remove archive ID : %s', archive['ArchiveId'].encode("utf-8"))
				try:
					vault.delete_archive(archive['ArchiveId'])
					logging.info('Successfully removed archive ID : %s', archive['ArchiveId'].encode("utf-8"))
				except:
					logging.error('Cannot remove archive ID : %s', archive['ArchiveId'].encode("utf-8"))

	logging.info('Removing vault…')
	try:
		vault.delete()
		logging.info('Vault removed.')
	except:
		logging.error('We can’t remove the vault now. Please wait some time and try again. You can also remove it from the AWS console, now that all archives have been removed.')

else:
	logging.info('Vault retrieval failed.')
