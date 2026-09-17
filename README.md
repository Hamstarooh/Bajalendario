# Bajalendario

A small desktop app to plan Dutch maternity and parental leave (**zwangerschaps-,
bevallings-, geboorte- en ouderschapsverlof**) for a couple, on a calendar.

Mark the days Mother and Father take off, see how many days/weeks are used
against the legal limits (with paid vs. unpaid weeks and the deadline by
which each type must be used), and export a plan to share with HR.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-informational)
![License](https://img.shields.io/badge/license-choose%20one-lightgrey)

## Features

- **Calendar view** with month navigation, separate colors per leave type,
  and the estimated due date highlighted.
- **Click a day** to open a quick "Add leave period" dialog pre-filled with
  that date — or use it to add a longer range at once (with a **+1 week**
  button to extend the end date quickly).
- **Fill a weekly pattern** (e.g. "every Friday" — a classic Dutch
  *papadag*) from a start date, automatically stopping once the legal limit
  or the deadline is reached.
- **Hard limits enforced**: the app will not let you mark more days than the
  law allows for each leave type.
- **Deadlines enforced**: e.g. additional partner leave must be used within
  6 months of birth, paid parental leave within the child's first year,
  unpaid parental leave before the child turns 8.
- **Paid vs. unpaid** weeks tracked separately for the 26-week parental leave
  (9 paid weeks + 17 unpaid weeks, per person).
- **Summary panel** with progress bars, and "First day" / "Last day" / "Reset"
  buttons per leave type.
- **Export for HR**: generates an HTML report (with a mini-calendar
  highlighting the start/end of every period, ready to print to PDF) and a
  CSV file — separately for Mother, for Father, and a combined version.
- All data is saved locally in `bajalendario_data.json`, next to the app.
  Nothing is sent anywhere.

## Leave types covered (Netherlands)

| Leave type | Weeks | Pay | Must be used by |
|---|---|---|---|
| Pregnancy & Maternity Leave (Mother) | 16 | 100% (UWV) | around birth |
| Parental Leave – Paid (Mother/Father) | 9 | 70% (UWV) | child's 1st birthday |
| Parental Leave – Unpaid (Mother/Father) | 17 | Unpaid | child's 8th birthday |
| Birth Leave (Father) | 1 | 100% (employer) | within 4 weeks of birth |
| Additional Partner Leave (Father) | 5 | 70% (UWV) | within 6 months of birth |

> These figures are indicative, based on standard Dutch entitlements at the
> time this app was written. Always confirm your exact entitlement with your
> employer's HR department and/or the UWV — collective agreements (CAO) can
> offer more.

## Running from source

Requires Python 3.9+ (Tkinter is included with standard Python on Windows/macOS;
on Linux you may need to install it separately, e.g. `sudo apt install python3-tk`).

```bash
python bajalendario.py
```

No external packages are required to run the app.

## Building the Windows .exe

The app can be packaged into a single standalone `.exe` (no Python required
on the target machine) using [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name Bajalendario bajalendario.py
```

The resulting executable is written to `dist/Bajalendario.exe`. It keeps its
data file (`bajalendario_data.json`) next to wherever the `.exe` is run from.

> Tip: binaries don't belong well in git history. Consider attaching
> `Bajalendario.exe` to a [GitHub Release](https://docs.github.com/en/repositories/releasing-projects-on-github)
> instead of committing it directly to the repository.

## Privacy note

`bajalendario_data.json` contains your leave planning (dates, due date). It
is excluded from version control by `.gitignore` so you don't accidentally
publish your personal planning when you push this repo.

## Publishing this project to GitHub

From inside this folder:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/bajalendario.git
git push -u origin main
```

(Create the empty repository on GitHub first, without a README, so the push
doesn't conflict.)

## Disclaimer

This tool is a personal planning aid, not legal or payroll advice. Leave
rules, percentages and deadlines can change or vary by employment contract —
always double-check with your employer and the UWV.

## License

No license has been chosen yet. Add a `LICENSE` file (e.g. MIT) if you want
to allow others to reuse this code.
