'''
Created on Oct 8, 2014

@author: Steven B. Nelson, Enterprise Infrastructure Architect
         NetApp, Inc

Wfa.py - WFA operational class
Contains the methods needed to execute WFA workflows remotely via REST protocol.

*** REQUIRES Python 2.7.x and above ***
*** IS NOT TESTED WITH Python 3.x ***
'''

class Wfa(object):
    '''
    This class provides all the required methods needed to call a generic workflow, given a small 
    amount of prior knowledge about the workflow needed to set this up.
    
    The first piece of knowledge is a username/password combination that has at least Operator privileges as defined 
    within the WFA software.  A default username/password combination is embedded currently and should be removed
    when implemented outside of a development environment as it is an invalid token.   Also the hostname that is hosting WFA
    and the full, human readable, workflow name is required.  
    
    Since WFA does not have a self describing API, and since the variables defined in the API are 
    arbitrarily named based on the whims of the creator of the workflow, both the names of the parameters and
    the intended values to be inserted into these names must be known prior to execution of the setupWorkflow and executeWorkflow
    method.  The mapping between the WFA parameter names and the values is defined by a dictionary with the following structure:
        Dictionary Key: WFA Parameter Name
        Dictionary Value: Value to pass to WFA for this parameter
        
    The two methods needed to execute workflows are: setupWorkflow and executeWorkflow.  The setupWorkflow requires the parameter map 
    listed above in order to prepare all the structures needed for execution.  The executeWorkflow takes the class variables 
    set by the setupWorkflow method and executes the workflow.
    
    Once the workflow is running, there is a method that can return a "simple" status of the job: getSimpleJobStatus.  This method returns
    either "OK", "FAILED", "DONE" or "UNKNOWN", depending on the lower level status returned by WFA.  This is structured this way to 
    prevent "over interpretation" of the intermediate status' provided by WFA - the essentially indicate that either a job is running
    ("OK"), a job is stopped prior to completion ("FAILED"), or a job completed ("DONE").  The "UNKNOWN" status is provided as a catch-all
    value.
    
    While the job is running, and at the conclusion of the job, state is maintained within a class dictionary: jobDict.  This dictionary
    stores such information as the jobId (WFA assigns this identifier), the current state of the job, the command number being executed
    and number of commands within the workflow, as well as any error codes and the values of any return parameters.
    
    In addition to providing the needed items to execute workflows, this class also provide two methods for discovering 
    the input and return structures of the workflow as defined.  These methods, printWorkflowInputList and printWorkflowOutputList
    simply require:
        1.    Instantiation of the class
        2.    Execution of a RESTful query using the getRestResponse method with the argument of the
                instance of the workflowQueryURI generated as a result of the class instantiation.  This will return raw XML
                back from the REST query
        3.    Execution of either/both methods with the raw XML resulting from item #2 above as the argument to the method
        
    The output will be the either the WFA variable name/data type/required status from WFA (in the case of InputList), or the name 
    of the return parameter (in the case of OutputList).  NOTE: The return parameter will ALWAYS be of type string.
    
    **** ENHANCEMENTS NEEDED ****
    1.    Data type handling - currently only String and Numeric types are handled.  Tables, Enum, and Boolean WFA data types are 
        currently not explicitly handled, although can be inserted if done correctly.  Enum values return a list of allowed values 
        for the input.  If the input value does not match one of the values in the list, WFA will throw a 500 HTTP error (Bad Response).
        Similarly for Boolean - it must be either 'true' or 'false' as a response.  Tables (Multi-Input) can be passed in the following 
        format (as an example 3x3 table):
        
        C1R1~C2R1~C3R1,C1R2~C2R2~C3R2,C1R3~C2R3~C3R3
        
        Data is entered as row dominant: rows are entered first, with columns separated by '~', with each individual row separated by a ','
    2.    Exception handling - there is essentially no exception handling currently.  Definite need.
    3.    Simple credentials - the urllib2 library only uses simply credentials.  Need to investigate how this operates with Keystone.
    4.    Allow for workflow UUIDs to be specified during instantiation vs. simply workflow names.
    5.    Insert logging...
    
    ***************************************************************************************************************************************
    Wfa class constructor
    
        wfaDict has the following structure (the same as the discrete arguments)
            wfaServer : <wfa server name> <mandatory> <string>
            wfaUser : <wfa user to execute workflow> <mandatory> <string>
            wfaPw : <password for wfa user> <mandatory key> <string>
            wfaParamMap : <mapping of workflow parameters with appropriate values> <mandatory> <dictionary>
            workflowName : <workflow name to execute> <mandatory> <string> 
                    
        Job dictionary.  Maintains state of the workflow job during
        execution.  Key defintions are:
            jobSelfLink - URI for the workflow job
            jobId - WFA assigned identifier to track the execution of the workflow
            jobStatus - Last reported status of the job
            jobError - Any error messages generated during a job failure.  This is only populated during failure
            wfCmdExecuting - The currently executing command number within the workflow (see WFA documentation)
            wfCmdTotal - The total number of commands within the workflow
            returnParams - a sub-dictionary containing:
                Key: Parameter Name being returned by the workflow
                Value: Value associated with the parameter name.
                Only populated after successful completion.
    '''

    def __init__(self, wfaServer=None, workflowName=None, wfaUser=None, wfaPw=None, wfaParamMap=None, wfaDict=None):
        import urllib
        
        # Instantiate class variable instances
        self.workflowInputXml = None
        self.wfaExecuteLink = None      
        
        
        if(wfaDict != None or type(wfaDict) == dict):
            self.wfaDict = wfaDict
        else:
            self.wfaDict = locals()

        self.jobDict = {
                        "jobSelfLink" : None,
                        "jobId" : None,
                        "jobStatus" : None,
                        "jobError" : None,
                        "wfCmdExecuting" : None,
                        "wfCmdTotal" : None,
                        "returnParams" : {}
                        }
        
        # Setup XML template
        self._baseXml = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <workflowInput>
        <userInputValues>--vk--
        </userInputValues>
    </workflowInput>
"""
        # Setup required URIs
        baseURI = "http://" + self.wfaDict['wfaServer'] + "/rest/workflows"
        self.workflowQueryURI = baseURI + "?name=" + urllib.quote_plus(self.wfaDict['workflowName'])
        
        # Set HTTP Header options
        self._workflowRestHeader = {
                      'content-type' : 'application/xml'
                      }        
        
        # Build the connection for this instantiation
        self._buildConnection(baseURI, self.wfaDict['wfaUser'], self.wfaDict['wfaPw'])
        
        return
    
    '''
    getWfaJobStatus - get the raw job status and update the job dictionary
    '''
    def getWfaJobStatus(self):
        
        # get the raw data by issuing a query against WFA
        jobXml = self.getRestResponse(self.jobDict['jobSelfLink'])
        
        '''
        The XML structure is documented in the WFA REST API Guide, and will not be documented here.  Sufficed to say, each element
        represents either an attribute or key value within the XML structure.
        '''
        self.jobDict['jobStatus'] = jobXml[1].find('jobStatus').text
        
        if(self.jobDict['wfCmdTotal'] == None):
            if(jobXml[1].find('workflow-execution-progress').find('commands-number') != None):
                self.jobDict['wfCmdTotal'] = jobXml[1].find('workflow-execution-progress').find('commands-number').text
        
        if(self.jobDict['wfCmdExecuting'] == None):
            if(jobXml[1].find('workflow-execution-progress').find('current-command-index') != None):
                self.jobDict['wfCmdExecuting'] = jobXml[1].find('workflow-execution-progress').find('current-command-index').text
        
        if(jobXml[1].find('errorMessage') != None):
            self.jobDict['jobError'] = jobXml[1].find('errorMessage').text
          
        '''
        Since there is a unknown number of return parameters, we simply loop until we run out, storing them all within
        the sub-dictionary in the job dictionary.
        '''  
        returnParamList = jobXml[1].findall('returnParameters')
        if(len(returnParamList) > 0):
            for returnParams in returnParamList:
                parameters = returnParams.find('returnParameters')
                self.jobDict['returnParams'][parameters.get('key')] = parameters.get('value')
        return
    
    '''
    getSimpleJobStatus - translate the raw WFA status' into a simple state that can be acted upon efficiently.
    '''
    def getSimpleJobStatus(self):
        
        '''
        There are three general catagories of state: bad, ok, and done.  We setup a list and then simply check to 
        see if our current status is in the list, then return the appropriate simple status.
        '''
        badStatus = ["FAILED", "ABORTING", "CANCELED", "OBSOLETE"]
        okStatus = ["PAUSED", "RUNNING", "PENDING", "SCHEDULED", "EXECUTING" ]
        doneStatus = "COMPLETED"
        self.getWfaJobStatus()
    
        if(self.jobDict['jobStatus'] == None):
            return("OK")
        
        if(self.jobDict['jobStatus'] in doneStatus):
            return("DONE")
        elif(self.jobDict['jobStatus'] in badStatus):
            return("FAILED")
        elif(self.jobDict['jobStatus'] in okStatus):
            return("OK")
        else:
            return("UNKNOWN")
    
    '''
    _buildInputXml - build the XML required for workflow submission.
    
    This method is intended to be private as it requires arguements that can only be provided internally.
    The input XML is the complete raw XML gathered from the initial REST query of WFA.  The wfaParamMap has the 
    mapping between the variables needed by the workflow and the values to be passed. 
    '''
    def _buildInputXml(self, wfaInputXml, wfaParamMap):
        # Generate the list of input values to iterate against.
        inputList = wfaInputXml[0].find('userInputList').findall('userInput')
        xmlString = ""
        # Iterate over all entries and build a XML key/value pair line.  Append the line to the existing collection 
        # of lines.
        for uInput in inputList:
            wfaParamName = uInput.find('name').text
            # Parameter name (WFA Parameter) is not in the map, this will currently fail.
            # However, if the map contains values not recogized by WFA, they will be silently skipped
            wfaParamValue = wfaParamMap[wfaParamName] 
            if(wfaParamValue != None):
                if(type(wfaParamValue) is not str):
                    wfaParamValue = str(wfaParamValue)
                xmlString = xmlString + "\n\t\t<userInputEntry key = \"" + wfaParamName + "\" value = \"" + wfaParamValue + "\"/>"
        # Replace the token in the XML template with the generated lines.  
        self.workflowInputXml = self._baseXml.replace('--vk--', xmlString)
        return
    '''
    printWorkflowInputList - print out a list of the inputs to the requested workflow
    '''
    def printWorkflowInputList(self, wfaInputXml):
        inputList = wfaInputXml[0].find('userInputList').findall('userInput')
        print "Name\t\t\t\tType\t\tMandatory"
        for uInput in inputList:
            print uInput.find('name').text + "\t\t\t" + uInput.find('type').text + "\t\t" + uInput.find('mandatory').text
        return
    '''
    printWorkflowOutputList - print out a list of the return parameters currently defined by the workflow
    '''
    def printWorkflowOutputList(self, wfaInputXml):
        inputList = wfaInputXml[0].find('returnParameters').findall('returnParameter')
        if(len(inputList) > 0):
            print "Parameters Returned"
            for returnParams in inputList:
                print returnParams.find('name').text
    
    '''
    _buildConnection - build the connection to be used for the RESTful API interaction
                        between this instance and WFA.
    
    Note that a) this is intended to be a private method, and b) this uses urllib2 with simple username/password 
    combinations - no pre-generated credential can be used with this library.
    '''
    def _buildConnection(self, baseURI, username, password):
        import urllib2   
        if(username == None):
            username = "admin"
        if(password == None):
            password = "sp1Tfir3"
        
        # WFA does define a realm, but does not enforce it - so why use it!
        pw_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        
        # We establish a credential for the /workflow/rest path.  Any child paths
        # using this credential will be honored.
        pw_manager.add_password(None, baseURI , username, password)
        handler = urllib2.HTTPBasicAuthHandler(pw_manager)
        opener = urllib2.build_opener(handler)
        
        # Install this instance for the instance of this class.
        urllib2.install_opener(opener)
        return
    
    '''
    _getWfaActionLink - retrieve the requested link out of the list of atoms provided by the raw workflow
    
    NOTE: The atoms must already be separated from the rest of the XML prior to calling this method.
    '''
    def _getWfaActionLink(self, linkToFind, atomList):
        for atomLink in atomList:
            if(atomLink.get('rel') == linkToFind):
                return(atomLink.get('href'))
     
    '''
    setupWorkflow - prepare to execute the workflow
    
    NOTE: The dictionary containing the mapping of WFA parameters to values is required for this.
    '''       
    def setupWorkflow(self, wfaParamMap=None):
        if(wfaParamMap == None and self.wfaDict['wfaParamMap'] == None):
            raise Exception("No WFA Parameters defined")
        elif(self.wfaDict['wfaParamMap'] != None and wfaParamMap == None):
            wfaParamMap = self.wfaDict['wfaParamMap']
                   
        # wfaUUID = wfaXml[0].get('uuid')
        # Get the raw XML from the initial query after opening the connection
        wfaXml = self.getRestResponse(self.workflowQueryURI)
        
        # set the execution link.  This allows the executeWorkflow to simply operate without arguments.
        self.wfaExecuteLink = self._getWfaActionLink('execute', wfaXml[0].findall('{http://www.w3.org/2005/Atom}link'))
        
        # build our XML to submit as part of the workflow.
        self._buildInputXml(wfaXml, wfaParamMap)
        return
    
    '''
    executeWorkflow - execute the workflow that has been setup by setupWorkflow.
    '''
    def executeWorkflow(self):
        from time import sleep
        # Get the raw XML from the execution request.  This raw XML contains the initial job information
        jobXml = self.getRestResponse(self.wfaExecuteLink, self.workflowInputXml, self._workflowRestHeader)
        sleep(5)
        # Set the values in the job dictionary for future use.
        self.jobDict['jobId'] = jobXml.get('jobId')
        self.jobDict['jobSelfLink'] = self._getWfaActionLink('self', jobXml.findall('{http://www.w3.org/2005/Atom}link'))
        return
    
    '''
    getRestResponse - generic method to return XML based on URIs passed to WFA.
    
    This has two optional parameters, depending on if you are issuing a GET or a POST.  The optional 
    parameters are used for the POST to WFA of the XML needed to initiate execution of the workflow
    '''
    def getRestResponse(self, URL, data=None, headers=None):
        import urllib2
        try:
            import xml.etree.cElementTree as ET
        except ImportError:
            import xml.etree.ElementTree as ET
        
        # if the data is specified, then issue this as a POST otherwise treat as a GET    
        if(data != None and headers != None):
            request = urllib2.Request(URL, data, headers)
        else:
            request = URL
        response = urllib2.urlopen(request).read()
        
        # Translate the raw string XML to something that is usable on the way back out.
        return(ET.fromstring(response))

class WfaOs(Wfa):
    '''
    WfaOs - OpenStack child class for Wfa
    
    This child class provides a method of providing a standard interface to WFA via some calls
    to construct the appropriate WFA call.  This class uses many of same inputs to the parent 
    class, except uses a dictionary to consolidate the call into a single argument.
    
    However, there are some fundamental differences.  In order to present a standard interface
    to OpenStack, and to prevent the necessity of hardcoding the workflow names into OpenStack, we
    have instead hard coded "default" workflow names within this class.  These default workflows
    provide the minimal amount of interface required between OpenStack and WFA to execute the various
    operations that are advertised by OpenStack.  As operations are added to OpenStack, they can be 
    added here as an additional specification using the class structure below as a template.
    
    The first implementation of this represent the Manila <-> WFA integration.  As additional workflows
    are defined for other projects within OpenStack, the class is setup for those definitions to be added.
    
    Additional parameters that may be optional to the base workflows can be specified via the 'wfaExtraSpec'
    dictionary that is embedded within the main dictionary argument.  Currently, these extra specs are provided
    within the manila.conf file as wfa_extra_spec = { <dictionary of specs> }.  This dictionary should be 
    structured as <WFA Parameter Name> : <Value to apply>  
    
    Instead of specifying individual workflow names, the class is instantiated by specifying an OpenStack operation
    to execute, a platform to execute against, and the OpenStack project calling the workflow.  This key ends up pointing to 
    both a standard workflow, and to the base WFA <-> OpenStack parameter map.  This map provides the method by 
    which OpenStack can pass parameters to WFA.  As with the base class, return parameters are passed via the jobDict
    dictionary.  
    
    If a non-standard workflow name is used, but will still use the same OpenStack standard parameters, then 
    the wfaDict['workflowName'] key can be populated with this new workflow name.  NOTE: The standard parameters are 
    not available for changing at this time.  In order to change both the workflow name and the parameters (without 
    altering this class directly), use the parent Wfa class and specify either a dictionary (as defined in the 
    class documentation) 
    
    After the class is instatiated, if there are extra specs to be added to the parameter map, use the appendExtraSpec()
    method to append these values.  This is separate from the initialization of the parameter map as the sample values 
    must be evaluated against the standard OpenStack parameters that would be set as part of the driver.
    
    ****************************************************************************************************************
    WfaOs class constructor
    
    This is the constructor for this child class.  The constructor takes a single argument - a dictionary with the
    following structure.
        wfaDict has the following structure:
            wfaServer : <wfa server name> <mandatory key> <string>
            wfaUser : <wfa user to execute workflow> <manadatory key> <string>
            wfaPw : <password for wfa user> <mandatory key> <string>
            wfaPlatform : <Enum of either 7m or cdot> 
            workflowName : <workflow name - overrides default workflow name> <string> 
            wfaOperation : <Enum of defined OpenStack operations
                            Manila:
                            create_share, delete_share, create_snapshot, delete_snapshot, create_nfs_share_snapshot,
                            grant_ip, deny_ip
                            ...others to follow...
                            >
            osProject : <Enum of OpenStack storage projects - currently [manila | cinder | swift]
            wfaExtraSpec : <dictionary of extra specs to insert into parameters map.  
                            extra specs must be passed as key/value pairs of the 
                            WFA Parameter as defined in the workflow, matched with the 
                            associated value>
    '''

    def __init__(self, wfaDict=None):

        # Setter...
        self.wfaDict = wfaDict
        
        '''
        Look at the OpenStack project being used in this instance.  Other projects can be implemented
        by simply creating the two methods listed below for the OpenStack project being implemented.
        See the method documentation.
        '''
        if(wfaDict['osProject'] == 'manila'):
            setWorkflows = self.setDefManilaWorkflows
            setWfaParamMap = self.getDefManilaParamMap
        else:
            raise Exception('OpenStack project' + wfaDict['osProject'] + 'not implemented...yet.')

        # If the workflow name is not defined, derive it from the operation requested.
        if(not 'workflowName' in self.wfaDict):        
            self.wfaDict['workflowName'] = setWorkflows()[self.wfaDict['wfaOperation']]
        elif(wfaDict['workflowName'] == None):
            self.wfaDict['workflowName'] = setWorkflows()[self.wfaDict['wfaOperation']]
        
        # Instantiate the base class    
        Wfa.__init__(self, wfaDict = self.wfaDict)
        
        # Install the generated parameter map.
        self.wfaDict['wfaParamMap'] = setWfaParamMap()
        return
    '''
    appendExtraSpec - append any extra specifications to the base parameter map after evaluation 
    of the template parameters.
    '''
    def appendExtraSpec(self):
        if(self.wfaDict['wfaExtraSpec'] != None and type(self.wfaDict['wfaExtraSpec']) == dict):
            for spec in self.wfaDict['wfaExtraSpec'].keys():
                self.wfaDict['wfaParamMap'][spec] = self.wfaDict['wfaExtraSpec'][spec]
        return
    
    '''
    setDefManilaWorkflows - set the workflow name for each platform type for Manila
    '''
    def setDefManilaWorkflows(self):
        if(self.wfaDict['wfaPlatform'] == '7m'):
            return( {
                           'create_share' : 'os_create_nfs_share_7m',
                           'delete_share' : 'os_delete_nfs_share_7m',
                           'create_snapshot' : 'os_create_snapshot_7m',
                           'delete_snapshot' : 'os_delete_snapshot_7m',
                           'create_share_snapshot' : 'os_create_nfs_share_snapshot_7m',
                           'delete_share_snapshot' : 'os_delete_nfs_share_snapshot_7m',
                           'grant_ip' : 'os_grant_ip_7m',
                           'deny_ip' : 'os_deny_ip_7m'
                           })
        elif(self.wfaDict['wfaPlatform'] == 'cdot'):
            return( {
                           'create_share' : 'os_create_nfs_share_cdot',
                           'delete_share' : 'os_delete_nfs_share_cdot',
                           'create_snapshot' : 'os_create_snapshot_cdot',
                           'delete_snapshot' : 'os_delete_snapshot_cdot',
                           'create_share_snapshot' : 'os_create_nfs_share_snapshot_cdot',
                           'delete_share_snapshot' : 'os_delete_nfs_share_snapshot_cdot',
                           'grant_ip' : 'os_grant_ip_cdot',
                           'deny_ip' : 'os_deny_ip_cdot'
                           })
        else:
            raise Exception("Invalid platform type")
    
    '''
    getDefManilaParamMap - return the default parameter map for the select Manila operation.
    '''    
    def getDefManilaParamMap(self):
        if(self.wfaDict['wfaOperation'] == 'create_share'):
            return({
                    'volSize' : 'shareSize',
                    'volName' : 'shareName',
                    'protocol' : 'shareProto'
                    })
        elif(self.wfaDict['wfaOperation'] == 'delete_share'):
            return({
                    'volName' : 'shareName'
                    })
        elif(self.wfaDict['wfaOperation'] == 'create_snapshot'):
            return({
                   'snapName' : 'snapID',
                   'volName' : 'shareName' 
                    })
        elif(self.wfaDict['wfaOperation'] == 'delete_snapshot'):
            return({
                   'snapName' : 'snapID'
                    })
        elif(self.wfaDict['wfaOperation'] == 'create_share_snapshot'):
            return({
                  'volSize' : 'shareSize',
                  'volName' : 'shareName',
                  'protocol' : 'shareProto',
                  'snapName' : 'snapID',
                  'sourceVolName' : 'origShareName' 
                    })
        elif(self.wfaDict['wfaOperation'] == 'grant_ip'):
            return({
                   'accessIP' : 'shareIP',
                   'wolName' : 'shareName',
                   'accessRule' : 'accessType' 
                    })
        elif(self.wfaDict['wfaOperation'] == 'deny_ip'):
            return({
                    'accessIP' : 'shareIP',
                    'volName' : 'shareName'
                    })
        else:
            return('Operation not implemented')
    