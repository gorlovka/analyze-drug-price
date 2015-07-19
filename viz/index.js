d3.json('data.json', function(error, data) {
    var pharmacies = data[0];
    var data = data[1];
    var items = [];
    for (var name in data) {
	var forms = data[name];
	for (var id in forms) {
	    var form = forms[id];
	    var pattern = form.pattern;
	    var title = form.title;
	    var amounts = form.amounts;
	    for (var amount in amounts) {
		var stats = amounts[amount];
		var limits = [];
		for (var form in stats.limits) {
		    var limit = stats.limits[form];
		    var price = limit[0];
		    var nds = limit[1];
		    var bulk = limit[2];
		    var retail = limit[3];
		    var delta = limit[4];
		    var value = limit[5];
		    limits.push({
			form: form,
			price: price,
			nds: nds,
			bulk: bulk,
			retail: retail,
			delta: delta,
			value: value
		    });
		}
		limits = limits.sort(function(a, b) {
		    return a.value - b.value;
		});
		var prices = [];
		for (var pharmacy in stats.prices) {
		    prices.push({
			pharmacy: pharmacies[pharmacy],
			value: stats.prices[pharmacy]
		    });
		}
		items.push({
		    name: name,
		    id: +id,
		    pattern: pattern,
		    title: title,
		    amount: +amount,
		    limits: limits,
		    prices: prices
		});
	    }
	}
    }
    items = items.sort(function(a, b) {
	var result = a.pattern.localeCompare(b.pattern);
	if (result == 0) {
	    result = b.amount - a.amount;
	}
	return result;
    });
    var columns = d3.selectAll('.column')[0];
    var capacity = Math.ceil(items.length / columns.length);
    items.forEach(function(item, index) {
	var column = columns[Math.floor(index / capacity)];
	column = d3.select(column);
	var card = column.append('div')
	    .attr('class', 'card')
	var description = card.append('div')
	    .attr('class', 'description')
	var pattern = description.append('div')
	    .attr('class', 'pattern')
	pattern.append('a')
	    .attr('href', ('http://med.sputnik.ru/description/'
			   + item.name + '/' + item.id))
	    .text(item.pattern);
	pattern.append('span')
	    .text(', ' + item.amount + 'шт.');

	var margin = {top: 15, right: 20, bottom: 20, left: 20};
	var width = 200 - margin.left - margin.right;
	var height = 60 - margin.top - margin.bottom;

	var svg = card
	    .append('svg')
	    .attr('class', 'chart')
	    .attr('width', width + margin.left + margin.right)
	    .attr('height', height + margin.top + margin.bottom)
	    .append('g')
	    .attr(
		'transform',
		'translate(' + margin.left + ',' + margin.top + ')'
	    );

	var prices = [];
	item.prices.forEach(function(price) {
	    prices.push(price.value);
	});
	var mean = d3.mean(prices);
	var median = d3.median(prices);
	var variation = d3.variance(prices);
	var sigma = Math.sqrt(variation)
	var extent = d3.extent(prices);
	var min = extent[0];
	var max = extent[1];

	var limit;
	for (var index in item.limits) {
	    limit = item.limits[index];
	    if (limit.value > max) {
		break;
	    }
	}

	var left = d3.max([mean - 3 * sigma, min]);
	var right = d3.max([mean + 3 * sigma, limit.value]);

	var excess = [];
	var nofit = [];
	var prices = [];
	item.prices.forEach(function(price) {
	    var value = price.value;
	    if (value > limit.value) {
		if (value <= right) {
		    excess.push(price);
		} else {
		    nofit.push(price);
		}
	    } else if (left <= value && value <= right) {
		prices.push(price);
	    }
	});

	var warn = excess.concat(nofit);
	if (warn.length > 0) {
	    warn = warn.sort(function(a, b) {
		return a.value - b.value;
	    });
	    var violations = description.append('ul')
		.attr('class', 'vialations');
	    var more = warn.length - 5;
	    warn.slice(0, 5).forEach(function(price, index) {
		var text = price.pharmacy + ' — ' + price.value + '₽';
		if (index == warn.length - 1 || index == 4) {
		    if (more > 0) {
			text += ' и ещё ' + more
		    }
		    text += '.'
		} else {
		    text += ';'
		}
		violations.append('li')
		    .attr('class', 'vialation')
		    .text(text);
	    });
	}

	var explain = description.append('div')
	    .attr('class', 'explain')
	explain.append('span')
	    .text(limit.value.toFixed(2) + '₽' + ' = (')
	explain.append('a')
	    .attr('href', ('http://grls.rosminzdrav.ru/PriceLims.aspx'
			   + '?PageSize=99&&Torg=' + item.title))
	    .text(limit.price + '₽')
	explain.append('span')
	    .text(' × ' + (1 + limit.nds) + ') × (1 + '
		  + limit.bulk + ' + ' + limit.retail + ')')
	if (limit.delta > 0) {
	    explain.append('span')
		.text(' + ' + limit.delta.toFixed(2) + '₽')
	}
	
	var domain = d3.extent(
	    prices.concat(excess, [limit]),
	    function(d) {
		return d.value;
	    }
	);
	left = d3.max([left, domain[0]]);
	right = d3.min([right, domain[1]]);

	var fit = 0;
	if (nofit.length > 0) {
	    fit = (right - left) / 10;
	}
	right += fit;

	var x = d3.scale.linear()
	    .range([0, width])
	    .domain([left, right]);
	
	var y = d3.scale.linear()
	    .range([height, 0])
	    .domain([0, height]);

	prices.forEach(function(price) {
	    var tick = {
		x: x(price.value),
		y1: y(0),
		y2: y(height / 2)
	    };
	    svg.append('line')
		.attr('class', 'rug price')
		.attr({
		    x1: tick.x,
		    y1: tick.y1,
		    x2: tick.x,
		    y2: tick.y2,
		})
	});
	    
	excess.forEach(function(price) {
	    var tick = {
		x: x(price.value),
		y1: y(0),
		y2: y(height / 2)
	    };
	    svg.append('line')
		.attr('class', 'rug price excess')
		.attr({
		    x1: tick.x,
		    y1: tick.y1,
		    x2: tick.x,
		    y2: tick.y2,
		})
	});

	nofit.forEach(function(price) {
	    var scale = d3.scale.linear()
		.range([0, fit])
		.domain([limit.value, max]);
	    var tick = {
		x: x(limit.value + scale(price.value)),
		y1: y(0),
		y2: y(height / 2)
	    };
	    svg.append('line')
		.attr('class', 'rug price excess')
		.attr({
		    x1: tick.x,
		    y1: tick.y1,
		    x2: tick.x,
		    y2: tick.y2,
		})
	})

	var tick = {
	    x: x(limit.value),
	    y1: y(0),
	    y2: y(height),
	    label: y(height + 2)
	};
	var group = svg.append('g')
	    .attr('class', 'rug limit')
	    .attr(
		'transform',
		'translate(' + tick.x + ',' + y(height) + ')'
	    );
	group.append('line')
	    .attr({
		x1: 0,
		y1: tick.y1,
		x2: 0,
		y2: tick.y2,
	    });
	var label = limit.value.toFixed(2) + '₽';
	group.append('text')
	    .attr({
		x: 0,
		y: tick.label
	    })
	    .text(label);

	var domain = [
	    Math.floor(Math.max(left, mean - 2 * sigma)),
	    Math.round(median),
	    Math.ceil(Math.min(right, mean + 2 * sigma))
	];
	var scale = d3.scale.ordinal()
	    .domain(domain)
	    .range(domain.map(x));
	var axis = d3.svg.axis()
	    .scale(scale)
	    .orient('bottom');

	svg.append('g')
	    .attr('class', 'axis')
	    .attr(
		'transform',
		'translate(' + 0 + ',' + y(-2) + ')'
	    )
	    .call(axis);
    });
});
