ymaps.ready(init);
var map;

function init() {
    var center = [55.76, 37.64];
    var zoom = 11;
    var active = null;
    map = new ymaps.Map ("map", {
        center: center,
        zoom: zoom,
	controls: ["smallMapDefaultSet"]
    });

    $.getJSON("data.json", function(data) {
	data.forEach(function(item) {
	    var content = "";
	    content += item.pharmacy + '<br/>'
	    content += item.address + '<br/>'
	    content += item.phone + '<br/>'
	    content += '<table>'
	    item.prices.forEach(function(item) {
		content += '<tr>'
		content += ('<td>' + item.form + ' #' +  item.amount + '</td>'
			    + '<td>' + item.price + 'р.' + '</td>'
			    + '<td>' + item.limit.toFixed(2) + 'р.' + '</td>')
		content += '</tr>'
	    });
	    content += '</table>'
	    var radius = Math.log(item.prices.length) * 10;
	    var circle = new ymaps.Circle([
		[item.lat, item.lon],
		radius
	    ], {
		balloonContent: content,
	    }, {
		draggable: false,
		fillColor: "#DB709377",
		strokeColor: "#DB709377",
		strokeOpacity: 1,
		strokeWidth: 5
	    });
	    map.geoObjects.add(circle);
	});
    });
}
