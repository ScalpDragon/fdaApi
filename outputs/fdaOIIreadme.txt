https://www.accessdata.fda.gov/scripts/ires/apidocs/

Code snippet to consume Enforcement Report API using python

#import required libraries
import requests
import json
import datetime

#create a signature and append it to the URL to avoid cached responses from server.
signature = str(int(datetime.datetime.now().timestamp()))

#set the url 
url = 'https://www.accessdata.fda.gov/rest/iresapi/recalls/?signature='+signature

#set headers
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'Authorization-User': 'Insert your Authorization-User here',
    'Authorization-Key': 'Insert your Authorization-Key here',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

#build the payload
data = 'payload={"displaycolumns": "productid,recalleventid,producttypeshort,firmcitynam,firmcountrynam,firmline1adr,firmline2adr,firmpostalcd,phasetxt,recallinitiationdt,firmlegalnam,voluntarytypetxt,distributionareasummarytxt,centercd,firmstateprvncnam,centerclassificationdt,terminationdt,initialfirmnotificationtxt,centerclassificationtypetxt,enforcementreportdt,firmfeinum,firmsurvivingnam,firmsurvivingfei,eventlmd,productdescriptiontxt,productshortreasontxt,recallnum,productdistributedquantity,determinationdt,postedinternetdt","filter":"[{\'eventlmdfrom\':\'07/24/2018\'},{\'eventlmdto\':\'09/24/2021\'},{\'centerclassificationtypetxt\':[\'3\',\'2\',\'1\',\'NC\']},{\'centercd\':[\'CBER\',\'CFSAN\']}]","start":1,"rows": 20,"sort":"productid","sortorder":"asc"}';

response = requests.post(url, headers=headers, data=data)

json = response.json()

print(json)
-----------
