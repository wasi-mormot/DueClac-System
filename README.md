# DueClac System

DueClac System is a Tkinter-based desktop application that converts text-copyable financial PDF reports into a filtered Excel due report.

## Features

- Upload a text-based PDF from the GUI
- Skip header noise before the report date range
- Detect groups and assign them to trader rows
- Rebuild multi-line trader names
- Skip duplicate table headers, subtotals, page numbers, and print date/time lines
- Filter only valid due-list traders
- Export a formatted Excel report with title, date range, totals, and bold headers

## Project Structure

```text
.
├── main.py
├── requirements.txt
├── README.md
└── dueclac
    ├── __init__.py
    ├── config.py
    ├── excel_exporter.py
    ├── gui.py
    ├── models.py
    ├── parser.py
    └── service.py
```

## Setup

1. Open PowerShell in this project folder.
2. Create a virtual environment:

```powershell
python -m venv .venv
```

3. Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

5. Run the app:

```powershell
python main.py
```

## How To Use

1. Click `Browse PDF` and choose the input PDF.
2. Click `Save As` and choose where the Excel file should be created.
3. Review the `Known Groups` box.
4. If a new PDF uses a new group name, add that group on a new line in the box before generating.
5. Click `Generate Excel`.
6. Wait for the success message.

## User Input Based Behavior

This project is already user-input based through the GUI:

- The user chooses the input PDF file.
- The user chooses the Excel save location.
- The user can edit the known group list before processing.

If you want to make it even more dynamic later, you can add:

- a checkbox for keeping or skipping empty groups
- a textbox for custom filter rules
- a preview table before export
- a save/load settings option for groups

## Business Rules Applied

Only rows that meet the due-list rules are exported:

- `Net Sales > Receive + Purchase`
- `Due > 0`
- `Net Sales > 0`
- `Opening != Due`

Rows are ignored when:

- `Net Sales <= 0`
- `Due <= 0`
- `Opening == Due`
- `Net Sales <= Receive + Purchase`

New Due formula:

```text
New Due = Net Sales - (Receive + Purchase + Payment + Discount)
```

## Notes About Parsing

- The parser starts considering report content only after the first detected date-range line.
- Group detection uses both your known-group list and fallback heuristics.
- When a new unknown group is incorrectly joined with a trader name, add that group to the GUI group list and run again.
- If a PDF is image-only rather than text-copyable, this version will not extract it correctly because OCR is not included.

## Upload To GitHub

1. Initialize git:

```powershell
git init
```

2. Create the main branch:

```powershell
git branch -M main
```

3. Add files:

```powershell
git add .
```

4. Commit:

```powershell
git commit -m "Initial DueClac System"
```

5. Create an empty repository on GitHub.
6. Copy the repository URL.
7. Add the remote:

```powershell
git remote add origin https://github.com/your-username/your-repo-name.git
```

8. Push:

```powershell
git push -u origin main
```

## Common GitHub Workflow After That

```powershell
git add .
git commit -m "Update parsing rules"
git push
```

