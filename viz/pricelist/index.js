d3.json('steps.json', function(error, data) {
    function plot(container, data) {
	var margin = {top: 10, right: 20, bottom: 40, left: 50},
	    width = 500 - margin.left - margin.right,
	    height = 300 - margin.top - margin.bottom;

	var x = d3.scale.linear()
	    .range([0, width]);

	var y = d3.scale.linear()
	    .range([height, 0]);

	var xAxis = d3.svg.axis()
	    .scale(x)
	    .orient('bottom');

	var yAxis = d3.svg.axis()
	    .scale(y)
	    .orient('left');

	var line = d3.svg.line()
	    .x(function(d) { return x(d.x); })
	    .y(function(d) { return y(d.y); });

	var svg = container.append('svg')
	    .attr('width', width + margin.left + margin.right)
	    .attr('height', height + margin.top + margin.bottom)
	    .append('g')
	    .attr('transform',
		  'translate(' + margin.left + ',' + margin.top + ')');

	x.domain(d3.extent(data, function(d) { return d.x; }));
	y.domain(d3.extent(data, function(d) { return d.y; }));

	svg.append('g')
	    .attr('class', 'x axis')
	    .attr('transform', 'translate(0,' + height + ')')
	    .call(xAxis)
	    .append('text')
	    .attr('x', width)
	    .attr('y', -6)
	    .style('text-anchor', 'end')
	    .text('Цена производителя, руб.');

	svg.append('g')
	    .attr('class', 'y axis')
	    .call(yAxis)
	    .append('text')
	    .attr('transform', 'rotate(-90)')
	    .attr('y', 6)
	    .attr('dy', '.71em')
	    .style('text-anchor', 'end')
	    .text('Ценник, руб.');

	svg.append('path')
	    .datum(data)
	    .attr('class', 'line')
	    .attr('d', line);
    }

    plot(d3.select('#steps'), data.steps);
    plot(d3.select('#smooth'), data.smooth);
});


d3.json('changes.json', function(error, data) {
    var margin = {top: 10, right: 20, bottom: 40, left: 50},
	width = 500 - margin.left - margin.right,
	height = 300 - margin.top - margin.bottom;

    var parse = d3.time.format("%Y-%m-%d").parse;

    var x = d3.time.scale()
	.range([0, width])
	.domain([parse('2010-11-11'), parse('2014-06-15')]);

    var y = d3.scale.linear()
	.range([height, 0])
	.domain([0.7, 1.5]);

    var xAxis = d3.svg.axis()
	.scale(x)
	.orient('bottom')
	.ticks(5);

    var yAxis = d3.svg.axis()
	.scale(y)
	.orient('left');

    var line = d3.svg.line()
	.x(function(d) { return x(d.date); })
	.y(function(d) { return y(d.y); });

    var svg = d3.select('#changes')
	.append('svg')
	.attr('width', width + margin.left + margin.right)
	.attr('height', height + margin.top + margin.bottom)
	.append('g')
	.attr('transform',
	      'translate(' + margin.left + ',' + margin.top + ')');

    svg.append('g')
	.attr('class', 'x axis')
	.attr('transform', 'translate(0,' + height + ')')
	.call(xAxis)

    svg.append('g')
	.attr('class', 'y axis')
	.call(yAxis)
	.append('text')
	.attr('transform', 'rotate(-90)')
	.attr('y', 6)
	.attr('dy', '.71em')
	.style('text-anchor', 'end')
	.text('Цена / начальная цена');

    data.forEach(function(series) {
	series.forEach(function(d) {
	    d.date = parse(d.date);
	});

	svg.append('path')
	    .datum(series)
	    .attr('class', 'line')
	    .attr('d', line);
    });
});


d3.json('sparks.json', function(error, data) {
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
    var columns = d3.selectAll('#sparks .column')[0];
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
	    .text(item.pattern + ', ' + item.amount + 'шт.');

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
	    	});
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
	    	});
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
	    	});
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
	var label = limit.value.toFixed(2) + 'р.';
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


var LOW = 0;
var MEDIUM = 1;
var HIGH = 2;


d3.json('data.json', function(error, data) {
    var titlesOrder = [];
    for (var title in data) {
	titlesOrder.push(title);
    }
    titlesOrder.sort(function(a, b) {
	return a.localeCompare(b);
    });
    var table = d3.select('#pricelist')
    var header = table.append('tr')
    header.append('th')
	.text('Название')
    header.append('th')
	.text('Форма, дозировка, упаковка')
    header.append('th')
	.text('Производитель')
    header.append('th')
	.text('Максимально допустимая цена')
    titlesOrder.forEach(function(title, index) {
	var titleCell = null;
	var titleCellSpan = 0;
	var forms = data[title];
	var formsOrder = [];
	for (var form in forms) {
	    formsOrder.push(form);
	}
	formsOrder.sort(function(a, b) {
	    return a.localeCompare(b);
	});
	formsOrder.forEach(function(form) {
	    var formCell = null;
	    var formCellSpan = 0;
	    var amounts = forms[form];
	    var amountsOrder = [];
	    for (var amount in amounts) {
		amountsOrder.push(amount);
	    }
	    amountsOrder.sort(function(a, b) {
		return a.localeCompare(b);
	    });
	    amountsOrder.forEach(function(amount) {
		var formAmount = form + ', ' + amount + ' шт.';
		var excessesProbability = amounts[amount].probability;
		var firms = amounts[amount].firms;
		var firmsOrder = [];
		for (var amount in firms) {
		    firmsOrder.push(amount);
		}
		firmsOrder.sort(function(a, b) {
		    return a.localeCompare(b);
		});
		firmsOrder.forEach(function(firm) {
		    var price = firms[firm];
		    price = price.toFixed(2) + 'р.';
		    var row = table.append('tr');
		    if (titleCell == null) {
			titleCell = row.append('td')
			    .text(title)
		    }
		    titleCellSpan += 1
		    titleCell.attr('rowspan', titleCellSpan)
		    if (formCell == null) {
			formCell = row.append('td')
			    .text(formAmount)
			if (excessesProbability != null) {
			    if (excessesProbability == LOW) {
				formCell.append('span')
				    .attr('class', 'text-muted')
				    .text(' Вероятность превышения низкая.')
			    } else if (excessesProbability == MEDIUM) {
				formCell.append('span')
				    .attr('class', 'text-warning')
				    .text(' Иногда встречаются превышения.')
			    } else if (excessesProbability == HIGH) {
				formCell.append('span')
				    .attr('class', 'text-danger')
				    .text(' Часто встречаются превышения.')
			    }
			}
		    }
		    formCellSpan += 1
		    formCell.attr('rowspan', formCellSpan)
		    row.append('td')
			.text(firm)
		    row.append('td')
			.text(price)
		});
	    });
	});
    });
});
