'use strict';
'require baseclass';
'require fs';
'require uci';

function metric(frontend, field, unit) {
	if (frontend.error)
		return _('Read failed');

	var value = frontend[field];
	if (value == null || value === '' || !isFinite(Number(value)))
		return _('Not supported');

	return Number(value).toFixed(2) + ' ' + unit;
}

function loadLine(section) {
	if (!section.device)
		return Promise.resolve({ device: '-', error: _('No device configured') });

	return L.resolveDefault(fs.exec_direct('/usr/sbin/ponctl',
		[ '--device', section.device, 'status', '--json' ]), null).then(function(output) {
		if (output == null)
			return { device: section.device, error: _('Device unavailable') };

		try {
			var snapshot = JSON.parse(output);
			if (snapshot.schema_version !== 1 || !snapshot.line)
				throw new Error('Invalid PON status');

			return { device: section.device, frontend: snapshot.frontend || {},
				active: snapshot.line.lifecycle === 'operational' };
		} catch (e) {
			return { device: section.device, error: _('Invalid status response') };
		}
	});
}

function renderLine(line) {
	var frontend = line.frontend || {};
	var fields = line.error ? [ _('Status'), line.error ] : [
		_('Receive optical power'), metric(frontend, 'rx_power_dbm', 'dBm'),
		_('Transmit optical power'), metric(frontend, 'tx_power_dbm', 'dBm'),
		_('PON temperature'), metric(frontend, 'temperature_celsius', '°C'),
		_('Supply voltage'), metric(frontend, 'voltage_volts', 'V'),
		_('Transmit bias current'), metric(frontend, 'tx_bias_ma', 'mA')
	];

	return E('div', { 'class': 'ifacebox' }, [
		E('div', { 'class': 'ifacebox-head center ' + (line.active ? 'active' : '') },
			E('strong', {}, line.device)),
		E('div', { 'class': 'ifacebox-body left' }, L.itemlist(E('span'), fields))
	]);
}

return baseclass.extend({
	title: _('PON optical module'),

	load: function() {
		return uci.load('pon').then(function() {
			return Promise.all(uci.sections('pon', 'xpon').map(loadLine));
		});
	},

	render: function(lines) {
		if (!lines.length)
			return null;

		return E('div', { 'class': 'network-status-table' }, lines.map(renderLine));
	}
});
