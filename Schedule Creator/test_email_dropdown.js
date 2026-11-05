async function runEmailDropdownTests(source) {
    new Function(source);
    const dialog = document.createElement('dialog');
    document.body.append(dialog);
    const runs = ['a', 'b'].map(id => ({
        id, location: 'Site ' + id, role: 'Cashier',
        start: '2026-11-02', end: '2026-11-08', revision: 1
    }));
    const groups = runs.map(run => ({
        location: {id: run.id, name: run.location},
        manager: {name: 'Manager ' + run.id, email: run.id + '@example.test'},
        runs: [run]
    }));
    let requests = 0, checks = 0;
    function check(condition, label) {
        if (!condition) throw new Error(label);
        checks++;
    }
    const section = source.slice(source.indexOf('function managerEmailPackage('),
        source.indexOf("document.addEventListener('change',e=>",
            source.indexOf('function managerEmailPackage(')));
    const harness = new Function('$', 'esc', 'appSettings', 'businessDeadline',
        'prettyDate', 'jamaicaDate', 'businessConfig', 'model', 'acceptedSchedules',
        'emailManagerGroups', 'select', 'directoryRequest', 'tenantAuthCsrfToken',
        section + ';return {openEmail,refreshEmailManagerGroups,prepareEmail};');
    const lookup = id => id === 'emailDialog' ? dialog : dialog.querySelector('#' + id);
    const api = harness(lookup, String, () => ({workforceCc: false, holidays: ''}),
        () => '2026-11-10', String, () => '2026-11-04', {}, {results: runs, selectedRun: 'a'},
        [{id: 'a'}], ids => {
            if (!ids.length) throw new Error('Select at least one schedule.');
            return groups.filter(group => ids.includes(group.location.id));
        }, () => '<select id="emailManagerGroup"></select>',
        async () => { requests++; return {codes: [{runId: 'a', locationId: 'a',
            role: 'Cashier', start: runs[0].start, end: runs[0].end, code: '000007',
            expiresAt: '2026-11-09T00:00:00-05:00'}]}; }, 'test-token');
    try {
        api.openEmail();
        check(lookup('emailManagerGroup').options.length === 1, 'Opening populates location');
        check(lookup('emailManagerGroup').value === 'a', 'Opening selects matching manager');
        check(requests === 0, 'Opening does not generate portal codes');
        dialog.querySelectorAll('[data-email-run]').forEach(input => { input.checked = true; });
        api.refreshEmailManagerGroups();
        check(lookup('emailManagerGroup').options.length === 2, 'Select all populates both locations');
        lookup('emailManagerGroup').value = 'b';
        api.refreshEmailManagerGroups();
        check(lookup('emailManagerGroup').value === 'b', 'Preserves selected location');
        check(lookup('emailManagerDetails').textContent.includes('b@example.test'), 'Manager details update');
        dialog.querySelectorAll('[data-email-run]').forEach(input => { input.checked = false; });
        api.refreshEmailManagerGroups();
        check(lookup('emailManagerGroup').disabled, 'Empty selection disables dropdown');
        check(lookup('emailError').textContent.includes('Select at least one'), 'Selection error visible');
        dialog.querySelector('[data-email-run]').checked = true;
        api.refreshEmailManagerGroups();
        check(!lookup('emailManagerGroup').disabled, 'Valid selection restores dropdown');
        const draft = await api.prepareEmail();
        check(draft.body.includes('Code: 000007'), 'Preview still includes portal code');
        return {checks, result: 'passed'};
    } finally {
        dialog.close();
        dialog.remove();
    }
}
