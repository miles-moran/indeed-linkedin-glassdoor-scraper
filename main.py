import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pprint
from lxml import html
import requests
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from datetime import datetime
from selenium.webdriver.common.keys import Keys
import re

settings = {
    "indeed_query": "",
    "id_stack": "",
    "id_role": "",
    "id_level": "",
}

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)

firmHeader = ["company", "id_link", "id_jobsopen", "id_software_jobsopen", "id_about", "gd_link", "gd_score", "li_link", "li_allstaff", "li_jobsopen"]
jobHeader =  ["company", "id_jobtitle",	"id_joblink", "id_jobdesc", "id_daysopen", "id_location", "id_contact", "id_apply", "id_role", "id_stack_primary", "id_stack_secondary", "id_level"]

def handleSettings():
    data = getSheetData("Settings")
    settings["indeed_query"] = data[0]["value"]
    settings["id_stack"] = data[1]["value"].lower().split(',')
    settings["id_role"] = data[2]["value"].lower().split(',')
    settings["id_level"] = data[3]["value"].lower().split(',')

def makeRequestAndGetTree(URL):
    headers = {
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36',
        'Accept-Language': 'en-gb',
        'Accept-Encoding': 'br, gzip, deflate',
        'Accept': 'test/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        r = requests.get(URL, headers=headers, timeout=10)
        print(r, "-", URL)
        tree = html.fromstring(r.content.decode("utf-8", "replace"))
        return tree
    except Exception as e:
        print(e)
        return None

def scrapeLinkedIn(browser, URL):
    data = {
        "li_allstaff": "",
        "li_jobsopen": ""
    }
    browser.get(URL+"/jobs")
    time.sleep(4)
    header = browser.find_element_by_xpath("//h4")
    header = header.text
    header = header.split("has ")
    header = header[1]
    header = header.split(" job openings")
    header = header[0]
    employees = browser.find_element_by_xpath("//span[@class='v-align-middle']")
    employees = employees.text
    employees = employees.split("See all")[1]
    employees = employees.split("employees")[0]
    data["li_allstaff"] = employees
    data["li_jobsopen"] = header
    return data

def analyzeText(title, description):
    title = title.lower()
    description = description.lower()
    spacedTitle = title.split(" ")
    spacedDescription = description.split(" ")
    
    data = {
        "email": "",
        "id_stack_primary": [],
        "id_stack_secondary": [],
        "id_role": [],
        "id_level": [],
    }

    numbers = "0123456789"
    spacedDescriptionNewLine = description.replace("\n", " ")
    spacedDescriptionNewLine = spacedDescriptionNewLine.split(" ")
    for i in range(0, len(spacedDescriptionNewLine)):
        s = spacedDescriptionNewLine[i]
        if "@" in s and (".com" in s or ".net" in s or ".org" in s):
            data["email"] = s
    removelist = "+-"

    pattern = re.compile(r'[^\w'+removelist+']')
    
    spacedDescription = pattern.split(description)
    spacedTitle = pattern.split(title)

    stack = {}
    
    for setting in settings["id_stack"]:
        count = 0
        if setting in spacedTitle:
            data["id_stack_primary"].append(setting)
        else: 
            for word in spacedDescription:
                    if setting == word:
                        count += 1
            if count > 0:
                stack[setting] = count
    
    stack = sorted(stack.items(), key=lambda x: x[1], reverse=True)
    new = []
    for s in stack:
        new.append(s[0])
    if len(data["id_stack_primary"]) == 0 and len(stack) != 0:
        data["id_stack_primary"].append(new.pop(0))
    data["id_stack_secondary"] = new

    for setting in settings["id_role"]:
        if setting not in data["id_role"]:
            if " " in setting:
                if setting in title:
                    data["id_role"].append(setting)
            else:
                if setting in spacedTitle:
                    data["id_role"].append(setting)
    
    for setting in settings["id_level"]:
        if setting not in data["id_level"]:
            if " " in setting:
                if setting in title:
                    data["id_level"].append(setting)
            else:
                if setting in spacedTitle:
                    data["id_level"].append(setting)

    data["id_stack_primary"] = arrayToCommaSeperated(data["id_stack_primary"])
    data["id_stack_secondary"] = arrayToCommaSeperated(data["id_stack_secondary"])
    data["id_role"] = arrayToCommaSeperated(data["id_role"])
    data["id_level"] = arrayToCommaSeperated(data["id_level"])  
    return data

def scrapeJobs(data):
    #LAUNCHING SELENIUM 
    options = Options()
    options.headless = True
    browser = webdriver.Chrome(executable_path='c:/chromedriver.exe', chrome_options=options)

    jobSpreadsheet = getSheetData("Jobs")
    url = data["url"]
    jobs = data["jobList"]['jobs']
    data = []
    for job in jobs:
        try:
            id_open = job["formattedRelativeTime"]
            id_open = id_open.replace("vor ", "")
            id_open = id_open.replace(" Tagen", "")
            j = {
                "id_open": id_open,
                "key": job["jobKey"],
                "id_location": job["location"],
                "id_title": job["title"],
                "id_joblink": url + "?jk=" + job["jobKey"],
                "company": job["companyName"],
                "id_jobdesc": "",
                "id_contact": "",
                "id_apply": "", 
                "id_role": "",
                "id_stack_primary": "",
                "id_stack_secondary": "",
                "id_level": "",
            }
            in_spreadsheet = False
            for s in jobSpreadsheet:
                if j["id_joblink"] == s["id_joblink"]:
                    j["id_jobdesc"] = s["id_jobdesc"]
                    j["id_apply"] = s["id_apply"]
                    j["id_role"] = s["id_role"]
                    j["id_stack_primary"] = s["id_stack_primary"]
                    j["id_stack_secondary"] = s["id_stack_secondary"]
                    j["id_level"] = s["id_level"]
                    j["id_contact"] = s["id_contact"]
                    in_spreadsheet = True
                    break

            if in_spreadsheet == False:
                print('New Job Posted')
                browser.get(j["id_joblink"])
                time.sleep(2)
                descriptionElement = browser.find_element_by_xpath("//div[@class='cmp-JobDetailDescription-description']")
                description = descriptionElement.text
                title = j["id_title"]
                apply = ""
                try:
                    applyElement = browser.find_element_by_xpath("//a[@data-tn-element='NonIAApplyButton']")
                    apply = applyElement.get_attribute("href")
                except Exception as e: 
                    errorLog(repr(e), "", "")
                analysis = analyzeText(title, description)
                j["id_jobdesc"] = description
                j["id_apply"] = apply
                j["id_contact"] = analysis["email"]
                j["id_stack_secondary"] = analysis["id_stack_secondary"]
                j["id_role"] = analysis["id_role"]
                j["id_level"] = analysis["id_level"]
                j["id_stack_primary"] = analysis["id_stack_primary"]
    
            data.append(j)
        except Exception as e: 
            errorLog(repr(e), "", "")
    return data

def scrapeFirms(data):
    f = {
        "id_about": "",
        "company": "",
        "id_jobsopen": 0
    }
    try:
        description = data["aboutStory"]["aboutDescription"]["lessText"]
        if "moreText" in data["aboutStory"]["aboutDescription"].keys():
            description += data["aboutStory"]["aboutDescription"]["moreText"]
        f["id_about"] = description
    except:
        pass

    try:
        f["company"] = data["topLocationsAndJobsStory"]["companyName"]
    except:
        pass

    try: 
        f["id_jobsopen"] = data["topLocationsAndJobsStory"]["totalJobCount"]
    except: 
        pass

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
            raw = raw.encode('utf-8')
            data = json.loads(raw, strict=False)
            pprint(data)
            break
    return data

def scrapeGlassdoor(url):
    tree = makeRequestAndGetTree(url)
    scripts = tree.xpath('//script[@type="application/ld+json"]')
    data = scripts[0].text
    data = data.split('ratingValue" : "')[1]
    data = data.split('",\n')[0]
    data.replace("'", '')    
    return data

def scrapeFirm(browser, firm):
    id_url = firm["id_link"]
    gd_url = firm["gd_link"]
    li_url = firm["li_link"]
    score = ""
    li_jobsopen = ""
    li_allstaff = ""
    count = 0
    data = {}
    if gd_url != "":
        try:
            score = scrapeGlassdoor(gd_url)
        except Exception as e:
            errorLog(repr(e), firm["id_link"], "")
    if li_url != "":
        try:
            data = scrapeLinkedIn(browser, li_url) 
            li_jobsopen = data["li_jobsopen"]
            li_allstaff = data["li_allstaff"]
            pass
        except Exception as e: 
            errorLog(repr(e), firm["id_link"], "")
    f = {}
    j = []
    data = {}
    try:
        data = scrapeIndeed(id_url)
        f = scrapeFirms(data)
    except Exception as e:
        errorLog(repr(e), firm["id_link"], "")
    time.sleep(1)
    id_url = firm["id_link"] + "/jobs?q=" + settings["indeed_query"]
    try:
        data = scrapeIndeed(id_url)
        data["url"] = firm["id_link"] + "/jobs"
        count = data["jobList"]["filteredJobCount"]
        j = scrapeJobs(data)
    except Exception as e:
        errorLog(repr(e), firm["id_link"], "")
    f["id_software_jobsopen"] = count
    f["gd_link"] = gd_url
    f["gd_score"] = score
    f["li_link"] = li_url
    f["li_jobsopen"] = li_jobsopen
    f["li_allstaff"] = li_allstaff
    f["jobs"] = j
    if firm["company"] != "":
        f["company"] = firm["company"]
    return f

def getSheetData(sheet):
    s = client.open("Indeed").worksheet(sheet)
    data = s.get_all_records()
    return data

def login(browser):
    browser.get("https://www.linkedin.com/login")
    time.sleep(2)
    username = browser.find_element_by_xpath('//input[@id="username"]')
    password = browser.find_element_by_xpath('//input[@id="password"]')
    username.send_keys("throwaway1993@live.com")
    password.send_keys("fukthaPoleece!911")
    browser.find_element_by_xpath('//button[@type="submit"]').click()
    
def getFirms(firms):
    harvested = []
    options = Options()
    # options.headless = True
    browser = webdriver.Chrome(executable_path='c:/chromedriver.exe', chrome_options=options)
    try:
        login(browser)
    except Exception as e: 
        errorLog(repr(e), "", "")
    time.sleep(5)
    for firm in firms:
        data = {}
        try: 
            data = scrapeFirm(browser, firm)
        except Exception as e:
            errorLog(repr(e), firm["id_link"], "")
        data["spreadsheet"] = firm
        harvested.append(data)
        time.sleep(5)
    return harvested
    
def writeToSheet(sheet, header, data):
    if len(data) > 0:
        s = client.open("Indeed").worksheet(sheet)
        book = client.open("Indeed")
        book.values_clear(sheet + "!A1:L10000")
        data.insert(0, header)
        cells = []
        for row_num, row in enumerate(data):
            for col_num, cell in enumerate(row):
                cells.append(gspread.Cell(row_num + 1, col_num + 1, data[row_num][col_num]))

        s.update_cells(cells)

def errorLog(error, firm, job):
    now = datetime.now() 
    time = now.strftime("%H:%M:%S, %m/%d/%Y")
    sheet = client.open("Indeed").worksheet('Log')
    sheet.append_row([time, error, firm, job])

def arrayToCommaSeperated(arr):
    new = ""
    for a in arr:
        new += a + ", "
    return new

def scrape():
    handleSettings()
    firmSpreadsheet = getSheetData("Firms")
    firmScrape = getFirms(firmSpreadsheet)
    jobs = []
    firms = []
    for firm in firmScrape:
        try:
            firms.append([firm["company"], firm["spreadsheet"]["id_link"], firm["id_jobsopen"], firm["id_software_jobsopen"], firm["id_about"], firm["gd_link"], firm["gd_score"], firm["li_link"], firm["li_allstaff"], firm["li_jobsopen"]])
            for job in firm["jobs"]:
                try:
                    jobs.append([job['company'], job['id_title'], job['id_joblink'], job["id_jobdesc"], job['id_open'], job['id_location'], job["id_contact"], job["id_apply"], job["id_role"], job["id_stack_primary"], job["id_stack_secondary"], job["id_level"]])
                except Exception as e:
                    errorLog(repr(e), "", )   
        except Exception as e:
            errorLog(repr(e), "", "")   
    
    writeToSheet("Jobs", jobHeader, jobs)
    writeToSheet("Firms", firmHeader, firms)

scrape()




