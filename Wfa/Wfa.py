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
    '''


    def __init__(self, wfaServer, workflowName, wfaUser=None, wfaPw=None):
        import urllib
        
        # Setter...       
        username = wfaUser
        password = wfaPw
        
        # Instantiate class variable instances
        self.workflowInputXml = ""
        self.wfaExecuteLink = ""
        
        '''
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
        baseURI = "http://" + wfaServer + "/rest/workflows"
        self.workflowQueryURI = baseURI + "?name=" + urllib.quote_plus(workflowName)
        
        # Set HTTP Header options
        self._workflowRestHeader = {
                      'content-type' : 'application/xml'
                      }        
        
        # Build the connection for this instantiation
        self._buildConnection(baseURI, username, password)
        
        return
    
    '''
    getWfaJobStatus - get the raw job status and update the job dictionary
    '''
    def getWfaJobStatus(self):
        
        # get the raw data by issuring a query against WFA
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
    def setupWorkflow(self, wfaParamMap):           
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
