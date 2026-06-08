#!/usr/bin/env python3
"""
Fix AdminDashboard: persist active tab in sessionStorage so navigating
away (to PatientHistory, Workspace) and back always returns to the same tab.
"""
path = '/home/ubuntu/scribe/frontend/src/pages/AdminDashboard.jsx'
with open(path) as f:
    c = f.read()

changes = 0

def rep(old, new, label):
    global c, changes
    if old in c:
        c = c.replace(old, new, 1)
        changes += 1
        print(f'OK: {label}')
    else:
        print(f'WARN not found: {label}')

# 1. Initialize tab from sessionStorage, add changeTab helper
rep(
    "  const [tab, setTab] = useState('providers');",
    (
        "  const [tab, setTab] = useState(\n"
        "    () => sessionStorage.getItem('adminTab') || 'providers'\n"
        "  );\n"
        "  // Persist active tab so navigating away and back restores the same tab\n"
        "  const changeTab = (t) => { sessionStorage.setItem('adminTab', t); setTab(t); };"
    ),
    'tab init from sessionStorage'
)

# 2. Replace all setTab calls in Tab onClick with changeTab
rep(
    "          <Tab active={tab === 'providers'} onClick={() => setTab('providers')}>Providers</Tab>\n"
    "          <Tab active={tab === 'templates'} onClick={() => setTab('templates')}>Note Templates</Tab>\n"
    "          <Tab active={tab === 'encounters'} onClick={() => setTab('encounters')}>All Encounters</Tab>",

    "          <Tab active={tab === 'providers'} onClick={() => changeTab('providers')}>Providers</Tab>\n"
    "          <Tab active={tab === 'templates'} onClick={() => changeTab('templates')}>Note Templates</Tab>\n"
    "          <Tab active={tab === 'encounters'} onClick={() => changeTab('encounters')}>All Encounters</Tab>",
    'Tab onClick → changeTab'
)

with open(path, 'w') as f:
    f.write(c)

print(f'\nDone: {changes} changes applied.')
