function runRosterValidationTests(source) {
    function extract(name) {
        const start = source.indexOf('function ' + name + '(');
        if (start < 0) throw new Error('Missing function: ' + name);
        const end = source.indexOf('\n}', start + 1);
        if (end < 0) throw new Error('Missing function end: ' + name);
        return source.slice(start, end + 2);
    }
    let checks = 0;
    function equal(actual, expected, label) {
        if (JSON.stringify(actual) !== JSON.stringify(expected)) {
            throw new Error(label + ': ' + JSON.stringify(actual));
        }
        checks++;
    }
    const pool = {id: 'Test|Cashier', location: 'Test', role: 'Cashier',
        shiftStarts: [6, 15], shares: [0.5, 0.5], enabled: true};
    const employee = {id: 'fixture', name: 'Test Employee', location: 'Test',
        role: 'Cashier', flex: 'Yes', reason: '', preferred: 6, proximity: 1,
        random: 1, attendance: null, allow: [null, null, null, null],
        shiftAvailability: {'6': 1, '15': 0}, days: [1, 1, 1, 1, 1, 1, 1]};
    const model = {roster: [employee], pools: [pool], locations: [], controls: {weeks: 1},
        results: [], sourceName: 'Fixture'};
    const fields = [['flex', 'Flexible'], ['reason', 'Reason if no'],
        ['preferred', 'Preferred start'], ['proximity', 'Proximity 1-3'],
        ['random', 'Random 1-3'], ['attendance', 'Attendance 0-100'],
        ...['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, i) => ['day' + i, day])];
    const functions = ['poolStarts', 'employeeCanStart', 'employeeStartPermission',
        'timeLabel', 'rosterErrors', 'poolRoster', 'inputTables'].map(extract).join('\n');
    const api = new Function('model', 'ROSTER_FIELDS', 'membershipFeatureEnabled',
        'const STARTS=[6,8.5,14,22],DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];' +
        'const key=(l,r)=>l+"|"+r,isNum=v=>v!==null&&Number.isFinite(Number(v)),sum=a=>a.reduce((x,y)=>x+y,0);' +
        functions + ';return {rosterErrors,employeeCanStart,inputTables};'
    )(model, fields, () => false);
    equal(api.rosterErrors(employee), [], 'Valid modern values ignore stale legacy blanks');
    employee.shiftAvailability['15'] = null;
    equal(api.rosterErrors(employee), ['Availability for 3:00 PM must be 0 or 1'],
        'Missing custom permission names the time');
    employee.shiftAvailability['6'] = null;
    employee.allow[0] = 1;
    equal(api.employeeCanStart(employee, 6), false, 'Explicit missing value cannot fall back to allowed');
    employee.shiftAvailability = {'6': 1, '15': 0};
    const tables = api.inputTables();
    equal(tables.Roster[0].length, tables.Roster[1].length, 'Export header matches row');
    equal(tables.Roster[1].slice(8, 12), [1, null, null, null],
        'Legacy export uses current permission, not stale values');
    equal(tables['Shift availability'].slice(1).map(row => row.slice(4)), [[6, 1], [15, 0]],
        'Export contains configured custom starts');
    equal(tables['Configured shift starts'].slice(1).map(row => row.slice(2)),
        [[6, 0.5], [15, 0.5]], 'Export preserves start shares');
    equal(tables['Location Roles'][0].length, tables['Location Roles'][1].length,
        'Legacy pool headers match custom-start row');
    equal(tables['Location Roles'][1].slice(3, 7), [0.5, 0, 0, 0],
        'Custom share does not shift into a legacy time column');
    const migrate = new Function('const STARTS=[6,8.5,14,22],key=(l,r)=>l+"|"+r;' +
        extract('scheduleWeeks') + '\n' + extract('migrateScheduleWeeks') +
        ';return migrateScheduleWeeks;')();
    const restored = JSON.parse(JSON.stringify(model));
    equal(api.rosterErrors(restored.roster[0], restored.pools[0]), [],
        'JSON reimport keeps corrected permissions');
    restored.roster[0].shiftAvailability['15'] = null;
    migrate(restored);
    equal(restored.roster[0].shiftAvailability['15'], null, 'Migration preserves explicit missing values');
    delete restored.roster[0].shiftAvailability['15'];
    migrate(restored);
    equal(restored.roster[0].shiftAvailability['15'], 0, 'New custom start defaults to disallowed');
    delete restored.roster[0].shiftAvailability['6'];
    migrate(restored);
    equal(restored.roster[0].shiftAvailability['6'], 1, 'Migration retains valid legacy permission');
    restored.roster[0].allow[0] = null;
    delete restored.roster[0].shiftAvailability['6'];
    migrate(restored);
    equal(restored.roster[0].shiftAvailability['6'], null, 'Missing legacy permission remains incomplete');
    const start = source.indexOf("else if(k.startsWith('start:'))");
    const end = source.indexOf("else if(k.startsWith('day'))", start);
    if (start < 0 || end < 0) throw new Error('Missing roster edit handler');
    const edit = new Function('r', 'k', 'v',
        'const STARTS=[6,8.5,14,22];' + source.slice(start + 5, end));
    edit(employee, 'start:6', '');
    equal(employee.shiftAvailability['6'], null, 'Blank selection stays missing');
    equal(employee.allow[0], null, 'Blank selection synchronises legacy permission');
    edit(employee, 'start:6', '0');
    equal(employee.allow[0], 0, 'No selection synchronises legacy permission');
    edit(employee, 'start:15', '1');
    equal(employee.shiftAvailability['15'], 1, 'Custom permission edit persists');
    return {checks, result: 'passed'};
}

if (typeof module !== 'undefined') {
    module.exports = runRosterValidationTests;
    if (require.main === module) {
        const fs = require('node:fs'), path = require('node:path');
        console.log(runRosterValidationTests(fs.readFileSync(path.join(__dirname, 'CBL-Scheduler2.js'), 'utf8')));
    }
}
