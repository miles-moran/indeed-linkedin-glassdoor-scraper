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

settings = {
    "indeed_query": "",
    "id_stack_primary": "",
    "id_stack_secondary": "",
    "id_role": "",
    "id_level": ""
}

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('creds.json', scope)
client = gspread.authorize(creds)

firmHeader = ["company", "id_link", "id_jobsopen", "id_software_jobsopen", "id_about", "gd_link", "gd_score", "li_link", "li_allstaff", "li_jobsopen"]
jobHeader =  ["company", "id_jobtitle",	"id_joblink", "id_jobdesc", "id_daysopen", "id_location", "id_contact", "id_apply", "id_role", "id_stack_primary", "id_stack_secondary", "id_level"]

def handleSettings():
    data = getSheetData("Settings")
    settings["indeed_query"] = data[0]["value"]
    settings["id_stack_primary"] = data[1]["value"].split(',')
    settings["id_stack_secondary"] = data[2]["value"].split(',')
    settings["id_role"] = data[3]["value"].split(',')
    settings["id_level"] = data[4]["value"].split(',')

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

def scrapeLinkedIn(browser, URL):
    browser.get(URL+"/jobs")
    time.sleep(4)
    header = browser.find_element_by_xpath("//h4")
    header = header.text
    header = header.split("has ")
    header = header[1]
    header = header.split(" job openings")
    header = header[0]
    pprint(header)
    return header

def analyzeText(title, description):
    spacedTitle = title.lower().split(" ")
    spacedDescription = description.lower().split(" ")
    data = {
        "email": "",
        "id_stack_primary": "",
        "id_stack_secondary": "",
        "id_role": "",
        "id_level": ""
    }

    for s in spacedTitle:
        for i in settings["id_stack_primary"]:
            if i.lower() == s and i.lower() not in  settings["id_stack_primary"]:
                data["id_stack_primary"] += i + ", "

    for s in spacedDescription:
        if "@" in s and (".com" in s or ".net" in s or ".org" in s):
            data["email"] = s
        for i in settings["id_stack_primary"]:
            if i.lower() == s and i.lower() not in settings["id_stack_primary"]:
                data["id_stack_primary"] += i + ", "
        for i in settings["id_stack_secondary"]:
            if i.lower() == s and i.lower() not in settings["id_stack_secondary"]:
                data["id_stack_secondary"] += i + ", "
        for i in settings["id_role"]:
            if i.lower() == s and i.lower() not in settings["id_role"]:
                data["id_role"] += i + ", "
        for i in settings["id_level"]:
            if i.lower() == s and i.lower() not in settings["id_level"]:
                data["id_level"] += i + ", "
                
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
            "id_stack_primary": "",
            "id_stack_secondary": "",
            "id_level": ""
        }
        in_spreadsheet = False
        for s in jobSpreadsheet:
            if j["id_joblink"] == s["id_joblink"]:
                j["id_jobdesc"] = s["id_jobdesc"]
                j["id_apply"] = s["id_apply"]
                j["id_role"] = s["id_role"]
                j["id_stack_primary"] = s["id_stack_primary"]
                j["id_stack_secondary"] = s["id_stack_secondary"]
                J["id_level"] = s["id_level"]
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
            except:
                pass
            analysis = analyzeText(title, description)
            j["id_jobdesc"] = description
            j["id_apply"] = apply
            j["id_contact"] = analysis["email"]
            j["id_stack_secondary"] = analysis["id_stack_secondary"]
            j["id_role"] = analysis["id_role"]
            j["id_level"] = analysis["id_level"]
            j["id_stack_primary"] = analysis["id_stack_primary"]
        data.append(j)
    return data

def scrapeFirms(data):
    description = ""
    if "aboutDescription" in data["aboutStory"].keys():
        description = data["aboutStory"]["aboutDescription"]["lessText"]
        if "moreText" in data["aboutStory"]["aboutDescription"].keys():
            description += data["aboutStory"]["aboutDescription"]["moreText"]
    id_jobsopen = data["topLocationsAndJobsStory"]["totalJobCount"]
    id_jobsopen.replace("vor ")
    id_jobsopen.replace(" Tagen")
    f = {
        "company": data["topLocationsAndJobsStory"]["companyName"],
        "id_jobsopen": id_jobsopen,
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
    if gd_url != "":
        score = scrapeGlassdoor(gd_url)
    if li_url != "":
        try:
            li_jobsopen = scrapeLinkedIn(browser, li_url)
        except Exception as e: 
            errorLog(repr(e), "", "")

    data = scrapeIndeed(id_url)
    f = scrapeFirms(data)

    time.sleep(1)

    id_url = firm["id_link"] + "/jobs?q=" + settings["indeed_query"]
    data = scrapeIndeed(id_url)
    data["url"] = firm["id_link"] + "/jobs"
    j = scrapeJobs(data)

    f["id_software_jobsopen"] = data["jobList"]["filteredJobCount"]
    f["jobs"] = j
    f["gd_link"] = gd_url
    f["gd_score"] = score
    f["li_link"] = li_url
    f["li_jobsopen"] = li_jobsopen
    f["li_allstaff"] = li_allstaff
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
    options.headless = True
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
            continue
        data["spreadsheet"] = firm
        harvested.append(data)
        time.sleep(5)
    return harvested
    
def writeToSheet(sheet, header, data):
    if len(data) > 0:
        s = client.open("Indeed").worksheet(sheet)
        s.clear()
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

def scrape():
    handleSettings()
    firmSpreadsheet = getSheetData("Firms")
    firmScrape = getFirms(firmSpreadsheet)
    jobs = []
    firms = []
    for firm in firmScrape:
        firms.append([firm["company"], firm["spreadsheet"]["id_link"], firm["id_jobsopen"], firm["id_software_jobsopen"], firm["id_about"], firm["gd_link"], firm["gd_score"], firm["li_link"], firm["li_allstaff"], firm["li_jobsopen"]])
        for job in firm["jobs"]:
            jobs.append([job['company'], job['id_title'], job['id_joblink'], job["id_jobdesc"], job['id_open'], job['id_location'], job["id_contact"], job["id_apply"], job["id_role"], job["id_stack_primary"], job["id_stack_secondary"], job["id_level"]])
    writeToSheet("Jobs", jobHeader, jobs)
    writeToSheet("Firms", firmHeader, firms)

scrape()
