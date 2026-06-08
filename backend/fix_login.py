#!/usr/bin/env python3
"""Fix Login.jsx: update demo credentials and make them clickable."""

path = '/home/ubuntu/scribe/frontend/src/pages/Login.jsx'
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

# 1. Fix email placeholder
rep(
    'placeholder="provider@scribe.demo"',
    'placeholder="sarah.chen@kyron.health"',
    'email placeholder'
)

# 2. Replace demo accounts section with clickable buttons that auto-fill
old_demo = (
    '          <div className="mt-4 pt-4 border-t border-clinical-border">\n'
    '            <p className="text-xs text-clinical-muted mb-2">Demo accounts:</p>\n'
    '            <div className="space-y-1 text-xs font-mono text-clinical-text-dim">\n'
    '              <div>dr.chen@scribe.demo / Provider1!</div>\n'
    '              <div>admin@scribe.demo / Admin123!</div>\n'
    '            </div>\n'
    '          </div>'
)

new_demo = (
    '          <div className="mt-4 pt-4 border-t border-clinical-border">\n'
    '            <p className="text-xs text-clinical-muted mb-2">Demo accounts <span className="text-clinical-accent/60">(click to fill)</span>:</p>\n'
    '            <div className="space-y-1">\n'
    '              {[\n'
    '                { label: "Admin", email: "admin@kyron.health", password: "Admin1234!" },\n'
    '                { label: "Dr. Chen", email: "sarah.chen@kyron.health", password: "Provider1234!" },\n'
    '                { label: "Dr. Rivera", email: "james.rivera@kyron.health", password: "Provider1234!" },\n'
    '                { label: "Dr. Patel", email: "emily.patel@kyron.health", password: "Provider1234!" },\n'
    '              ].map(acc => (\n'
    '                <button\n'
    '                  key={acc.email}\n'
    '                  type="button"\n'
    '                  onClick={() => { setEmail(acc.email); setPassword(acc.password); }}\n'
    '                  className="w-full text-left px-2 py-1 rounded hover:bg-clinical-border/30 transition-colors"\n'
    '                >\n'
    '                  <span className="text-xs font-semibold text-clinical-text-dim w-16 inline-block">{acc.label}</span>\n'
    '                  <span className="text-xs font-mono text-clinical-muted">{acc.email}</span>\n'
    '                </button>\n'
    '              ))}\n'
    '            </div>\n'
    '          </div>'
)

rep(old_demo, new_demo, 'demo accounts clickable')

with open(path, 'w') as f:
    f.write(c)

print(f'\nDone: {changes} changes applied.')
