#!/usr/bin/python

"""
Nagios plugin which checks json values from a given endpoint against argument specified rules
and determines the status data for that service.  The JSON document is flattened into properties
such that {category: {foo : {status: "ALARM"}}} becomes category.foo.status=ALARM.  Regular
expressions are then applied to these property names.  The level argument is to provide added context
in the output; If a property such as "category.foo.status=ALARM, then it could be useful to know
the sibling of status, which might be "category.foo.id=module1".  Setting level to 1 would output
category.foo.status=ALARM as well as category.foo.id=module1
"""

import httplib, urllib, urllib2, base64
import json
import argparse
import sys
import re
from pprint import pprint
from urllib2 import HTTPError
from urllib2 import URLError


OK_CODE = 0
WARNING_CODE = 1
CRITICAL_CODE = 2
UNKNOWN_CODE = 3

def parseArgs():
	parser = argparse.ArgumentParser(description=
			'Nagios plugin which checks json values from a given endpoint against argument specified rules\
			and determines the status data for that service.  The JSON document is flattened into properties\
			such that {category: {foo : {status: "ALARM"}}} becomes category.foo.status=ALARM.  Regular \
			expressions are then applied to these property names.  The level argument is to provide added context\
			in the output; If a property such as "category.foo.status=ALARM, then it could be useful to know \
			the sibling of status, which might be "category.foo.id=module1".  Setting level to 1 would output\
			category.foo.status=ALARM as well as category.foo.id=module1')

	parser.add_argument('-q', '--key_equals', dest='key_value_list', nargs='*',
	help='Checks equality of these key regular expressions and values (key_regex,value,level key2_regex,value2,level) to determine status.\
	Multiple key values can be delimited with colon (key_regex,value1:value2,level). Return warning if equality check fails')

	parser.add_argument('-Q', '--key_equals_critical', dest='key_value_list_critical', nargs='*',
	help='Same as -q but return critical if equality check fails.')

	parser.add_argument('-e', '--key_exists', dest='key_list', nargs='*',
	help='Checks existence of these key regular expressions to determine status (key_regex). Return warning if key is not present.')

	parser.add_argument('-E', '--key_exists_critical', dest='key_list_critical', nargs='*',
	help='Same as -e but return critical if key is not present.')

	parser.add_argument('-w', '--warning', dest='key_threshold_warning', nargs='*',
	help='Warning threshold for these values (key1_regex,WarnRange,level key2_regex,WarnRange,level). WarnRange is in the format [@]start:end, more information at nagios-plugins.org/doc/guidelines.html.')

	parser.add_argument('-c', '--critical', dest='key_threshold_critical', nargs='*',
	help='Critical threshold for these values (key1_regex,CriticalRange,level key2,CriticalRange,level. CriticalRange is in the format [@]start:end, more information at nagios-plugins.org/doc/guidelines.html.')

	parser.add_argument('-v', '--verbose', action='store_true', help='Verbose Output')
	parser.add_argument('-d', '--debug', action='store_true', help='Debug mode.')
	parser.add_argument('-s', '--ssl', action='store_true', help='HTTPS mode.')
	parser.add_argument('-H', '--host', dest='host', required=True, help='Host.')
	parser.add_argument('-P', '--port', dest='port', help='TCP port')
	parser.add_argument('-p', '--path', dest='path', help='Path.')
	parser.add_argument('-t', '--timeout', type=int, help='Connection timeout (seconds)')
	parser.add_argument('-B', '--basic-auth', dest='auth', help='Basic auth string "username:password"')

	return parser.parse_args()

def debugPrint(debug_flag, message, pretty_flag=False):
	if debug_flag:
		if pretty_flag:
			pprint(message)
		else:
			print message

class NagiosHelper:
	"""Help with Nagios specific status string formatting."""
	message_prefixes = {OK_CODE: 'OK', WARNING_CODE: 'WARNING', CRITICAL_CODE: 'CRITICAL', UNKNOWN_CODE: 'UNKNOWN'}
	performance_data = ''
	warning_message = ''
	critical_message = ''
	unknown_message = ''

	def getMessage(self):
		"""Build a status-prefixed message with optional performance data generated externally"""
		text = "%s: Status %s. ;" % (self.message_prefixes[self.getCode()], self.message_prefixes[self.getCode()])
		if (self.warning_message != '') :
			text += (" Warnings: %s" % self.warning_message)
		if (self.critical_message != '') :
			text += (" Critical: %s" % self.critical_message)
		if (self.unknown_message != '') :
			text += (" Unknown: %s" % self.unknown_message)
		if self.performance_data:
			text += "Performance Data: |%s" % self.performance_data

		return text

	def getCode(self):
		code = OK_CODE
		if (self.warning_message != ''):
			code = WARNING_CODE
		if (self.critical_message != ''):
			code = CRITICAL_CODE
		if (self.unknown_message != ''):
			code = UNKNOWN_CODE
		return code

	def appendWarning(self, warnings) :
		if (isinstance(warnings, str)) :
			warnings = [warnings]

		for warning in warnings :
			self.warning_message += (warning + "; ")

	def appendCritical(self, criticals) :
		if (isinstance(criticals, str)) :
			criticals = [criticals]

		for critical in criticals :
			self.critical_message += (critical + "; ")

	def appendUnknown(self, unknowns):
		if (isinstance(unknowns, str)) :
			unknowns = [unknowns]

		for unknown in unknowns :
			self.unknown_message += (unknown + "; ")

	def appendMetrics(self, (performance_data, warning_message, critical_message)):
		self.performance_data += performance_data
		self.append_warning(warning_message)
		self.append_critical(critical_message)

def flattenJson(dictionary, base, idx = -1, parsedProperties = dict()) :
	"""Given a dictionary of parsed JSON, flatten into key/value properties dictionary"""
	for key in dictionary :
		value = key
		if isinstance(dictionary, dict) :
			value = dictionary[key]

		newbase = "%s.%s" % (base, key)
		if (idx >= 0) :
			newbase = "%s.[%d].%s" % (base, idx, key)

		if (isinstance(key, dict)) :
			flattenJson(key, base, dictionary.index(key), parsedProperties)
		elif (isinstance(value, list)) :
			flattenJson(value, newbase, -1, parsedProperties)
		elif isinstance(value, dict) :
			flattenJson(value, newbase, -1, parsedProperties)
		else :
			# trim leading '.'
			parsedProperties[newbase[1:]] = value

class JsonRuleProcessor :
	"""Provides basic rule checking of regular expressions against parsed/flattened JSON."""
	def __init__(self, parsedProperties, applicationArgs):
		self.parsedProperties = parsedProperties
		self.applicationArgs = applicationArgs

	def checkKeyValue(self, keyValueList, valueChecker) :
		failure = list()
		if (keyValueList == None) :
			return failure

		for parsedKey, parsedValue in self.parsedProperties.iteritems() :
			for keyValueArg in keyValueList :
				keyRegex, expectedValue, contextLevels = keyValueArg.split(',')

				if (re.match(keyRegex, parsedKey) and valueChecker(parsedKey, parsedValue, expectedValue)) :
					failure.append(self.formatContext(parsedKey, parsedValue, int(contextLevels)))

		return failure

	def checkExists(self, keyList) :
		foundKeyList = list()
		if (keyList == None) :
			return list()

		# Non-variable context level, only the missing key will be reported.
		contextLevel = 1

		for parsedKey in self.parsedProperties :
			notFoundKeyList = filter(lambda key: key not in foundKeyList, keyList)
			for keyRegex in notFoundKeyList :

				if (re.match(keyRegex, parsedKey)) :
					foundKeyList.append(keyRegex)

		failure = list()

		notFoundKeyList = filter(lambda key: key not in foundKeyList, keyList)
		for keyRegex in notFoundKeyList :
			failure.append(self.formatContext(keyRegex, None, contextLevel))

		return failure

	def formatContext(self, key, value, contextLevels) :
		keyParts = key.split('.')
		keyParts = keyParts[0:len(keyParts) - contextLevels]
		keyParent = str.join('.', keyParts)

		if (value == None) :
			msg = ' %s Not Found' % (key)
		else :
			msg = ' %s=%s' % (key, value)

		for parsedKey in self.parsedProperties :
			if (parsedKey.startswith(keyParent) and parsedKey != key) :
				msg += '; %s=%s' % (parsedKey, self.parsedProperties[parsedKey])

		return msg

	def literalValueChecker(self, parsedKey, parsedValue, expectedExpression) :
		"""Checks the given value against a colon delimitted set of values"""
		expectedValues = expectedExpression.split(':')
		return parsedValue not in expectedValues

	def valueRangeChecker(self, parsedKey, parsedValue, expectedExpression) :
		"""Checks the given value against a nagios-formatted range expression"""
		invert = False
		start = 0
		end = None
		value = int(parsedValue)

		debug = self.applicationArgs.debug

		if expectedExpression.startswith('@'):
			invert = True
			expectedExpression = expectedExpression[1:]

		vals = expectedExpression.split(':')
		if len(vals) == 1:
			end = vals[0]
		if len(vals) == 2:
			start = vals[0]
			if vals[1] != '':
				end = vals[1]

		if(start == '~'):
			if (invert and value <= int(end)):
				debugPrint(debug, " Value for key %s was less than or equal to %s." % (parsedKey, end))
				return True
			elif (not invert and value > int(end)):
				debugPrint(debug, " Value for key %s was greater than %s." % (parsedKey, end))
				return True
		elif(end == None):
			if (invert and value >= int(start)):
				debugPrint(debug, " Value for key %s was greater than or equal to %s." % (parsedKey, start))
				return True
			elif (not invert and value < int(start)):
				debugPrint(debug, " Value for key %s was less than %s." % (parsedKey, start))
				return True
		else:
			if (invert and value >= int(start) and value <= int(end)):
				debugPrint(debug, " Value for key %s was inside the range %s:%s." % (parsedKey, start, end))
				return True
			elif (not invert and ((value < int(start)) or (value > int(end)))):
				debugPrint(debug, " Value for key %s was outside the range %s:%s." % (parsedKey, start, end))
				return True

		return False


	def checkWarnings(self) :
		warnings = list()
		warnings.extend(self.checkKeyValue(self.applicationArgs.key_value_list, self.literalValueChecker))
		warnings.extend(self.checkKeyValue(self.applicationArgs.key_threshold_warning, self.valueRangeChecker))
		warnings.extend(self.checkExists(self.applicationArgs.key_list))
		return warnings

	def checkCriticals(self) :
		criticals = list()
		criticals.extend(self.checkKeyValue(self.applicationArgs.key_value_list_critical, self.literalValueChecker))
		criticals.extend(self.checkKeyValue(self.applicationArgs.key_threshold_critical, self.valueRangeChecker))
		criticals.extend(self.checkExists(self.applicationArgs.key_list_critical))
		return criticals


if __name__ == "__main__":
	args = parseArgs()
	nagios = NagiosHelper()
	if args.ssl:
		url = "https://%s" % args.host
	else:
		url = "http://%s" % args.host
	if args.port: url += ":%s" % args.port
	if args.path: url += "/%s" % args.path
	debugPrint(args.debug, "url:%s" % url)
	# Attempt to reach the endpoint
	try:
		req = urllib2.Request(url)
		if args.auth:
			base64str = base64.encodestring(args.auth).replace('\n', '')
			req.add_header('Authorization', 'Basic %s' % base64str)
		if args.timeout and args.data:
			response = urllib2.urlopen(req, timeout=args.timeout, data=args.data)
		elif args.timeout:
			response = urllib2.urlopen(req, timeout=args.timeout)
		else:
			response = urllib2.urlopen(req)
	except HTTPError as e:
		nagios.appendUnknown("HTTPError[%s], url:%s" % (str(e.code), url))
	except URLError as e:
		nagios.appendCritical("URLError[%s], url:%s" % (str(e.reason), url))
	else:
		jsondata = response.read()

		dictionary = json.loads(jsondata)
		parsedProperties = dict()
		flattenJson(dictionary, "", -1, parsedProperties)

		debugPrint(args.debug, "Parsed Properties:")
		for key in parsedProperties :
			debugPrint(args.debug, "%s=%s" % (key, parsedProperties[key]))

		processor = JsonRuleProcessor(parsedProperties, args)
		nagios.appendWarning(processor.checkWarnings())
		nagios.appendCritical(processor.checkCriticals())

	print nagios.getMessage()
	exit(nagios.getCode())
