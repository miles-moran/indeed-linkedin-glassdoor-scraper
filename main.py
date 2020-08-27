import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from lxml import html
import requests
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)

firmHeader = ["company", "id_link", "id_jobsopen", "id_software_jobsopen", "id_about", "gd_link", "gd_score", "li_link", "li_allstaff", "li_jobsopen"]
jobHeader =  ["company", "id_jobtitle",	"id_joblink", "id_jobdesc", "id_daysopen", "id_location", "id_contact", "id_apply", "id_issoftware", "id_role", "id_stack_primary", "id_stack_secondary", "id_isalive"]

def makeRequestAndGetTree(URL):
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36',
        'Accept-Language': 'en-gb',
        'Accept-Encoding': 'br, gzip, deflate',
        'Accept': 'test/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        r = requests.get(URL, headers=headers, timeout=5)
        print(r)
        tree = html.fromstring(r.content.decode("utf-8", "replace"))
        return tree
    except Exception as e:
        print(e)
        return None

def analyseDescription(description):
    spaced = description.split(" ")
    data = {
        "email": ""
    }
    for s in spaced:
        if "@" in s and (".com" in s or ".net" in s or ".org" in s):
            data["email"] = s
    return data

def scrapeJobs(data):
    #LAUNCHING SELENIUM 
    browser = webdriver.Chrome(executable_path='c:/chromedriver.exe')

    jobSpreadsheet = getSheetData("Jobs")
    url = data["url"]
    jobs = data["jobList"]['jobs']
    data = []
    for job in jobs:
        j = {
            "id_open": job["formattedRelativeTime"],
            "key": job["jobKey"],
            "id_location": job["location"],
            "id_title": job["title"],
            "id_joblink": url + "?jk=" + job["jobKey"],
            "company": job["companyName"],
            "id_jobdesc": "",
            "id_contact": "",
            "id_apply": "", 
            "id_role": "",
            "id_issoftware": "",
            "id_isalive": "",
            "id_stack_primary": "",
            "id_stack_secondary": "",
            "id_isalive": ""
            
        }
        in_spreadsheet = False
        for s in jobSpreadsheet:
            if j["id_joblink"] == s["id_joblink"]:
                j["id_jobdesc"] == s["id_jobdesc"]
                j["id_apply"] == s["id_apply"]
                j["id_issoftware"] == s["id_issoftware"]
                j["id_role"] == s["id_role"]
                j["id_isalive"] == s["id_isalive"]
                j["id_stack_primary"] == s["id_stack_primary"]
                j["id_stack_secondary"] == s["id_stack_secondary"]
                j["id_contact"] = s["id_contact"]
                in_spreadsheet = True
                break

        if in_spreadsheet == False:
            print('New Job Posted')
            browser.get(j["id_joblink"])
            time.sleep(2)

            descriptionElement = browser.find_element_by_xpath("//div[@class='cmp-JobDetailDescription-description']")
            description = descriptionElement.text
            apply = ""
            try:
                applyElement = browser.find_element_by_xpath("//a[@data-tn-element='NonIAApplyButton']")
                apply = applyElement.get_attribute("href")
            except:
                pass
            analysis = analyseDescription(description)
            j["id_jobdesc"] = description
            j["id_apply"] = apply
            j["id_contact"] = analysis["email"]

        data.append(j)

    return data

def scrapeFirms(data):
    description = ""
    if "aboutDescription" in data["aboutStory"].keys():
        description = data["aboutStory"]["aboutDescription"]["lessText"]
    f = {
        "company": data["topLocationsAndJobsStory"]["companyName"],
        "id_jobsopen": data["topLocationsAndJobsStory"]["totalJobCount"],
        "id_about": description,
    }
    return f

def scrapeIndeed(url):
    tree = makeRequestAndGetTree(url)
    scripts = tree.xpath('//script')
    data = {}
    for script in scripts:
        raw = script.text
        if "window._initialData=JSON.parse('" in str(raw):
            raw = raw.split("window._initialData=JSON.parse('")[1]
            raw = raw.split("');")[0]
            raw = raw.encode('ascii', 'ignore').decode('unicode_escape')
            data = json.loads(raw, strict=False)
            break
    return data

def scrapeFirm(firm):
    url = firm["id_link"]
    data = scrapeIndeed(url)
    f = scrapeFirms(data)

    time.sleep(1)

    url = firm["id_link"] + "/jobs?q=software"
    data = scrapeIndeed(url)
    data["url"] = firm["id_link"] + "/jobs"
    j = scrapeJobs(data)

    f["id_software_jobsopen"] = data["jobList"]["filteredJobCount"]
    f["jobs"] = j
    return f

def getSheetData(sheet):
    s = client.open("Indeed").worksheet(sheet)
    data = s.get_all_records()
    return data
    
def getFirms(firms):
    harvested = []
    for firm in firms:
        data = scrapeFirm(firm)
        data["spreadsheet"] = firm
        harvested.append(data)
        time.sleep(5)
    return harvested
    
def writeToSheet(sheet, header, data):
    s = client.open("Indeed").worksheet(sheet)
    s.clear()
    data.insert(0, header)
    cells = []
    for row_num, row in enumerate(data):
        for col_num, cell in enumerate(row):
            cells.append(gspread.Cell(row_num + 1, col_num + 1, data[row_num][col_num]))

    s.update_cells(cells)


def scrape():
    firmSpreadsheet = getSheetData("Firms")
    firmScrape = getFirms(firmSpreadsheet)
    jobs = []
    firms = []
    for firm in firmScrape:
        firms.append([firm["company"], firm["spreadsheet"]["id_link"], firm["id_jobsopen"], firm["id_software_jobsopen"], firm["id_about"]])
        for job in firm["jobs"]:
            jobs.append([job['company'], job['id_title'], job['id_joblink'], job["id_jobdesc"], job['id_open'], job['id_location'], job["id_contact"], job["id_apply"], job["id_issoftware"], job["id_role"], job["id_stack_primary"], job["id_stack_secondary"], job["id_isalive"]])
    writeToSheet("Jobs", jobHeader, jobs)
    writeToSheet("Firms", firmHeader, firms)

scrape()
