// temporal_charts.js - Code của Thành viên 3

// Cấu hình kích thước chung
const margin = { top: 30, right: 30, bottom: 50, left: 60 };
const width = 900 - margin.left - margin.right;
const height = 350 - margin.top - margin.bottom;

const tooltip = d3.select("#tooltip");
const colorScale = d3.scaleOrdinal().domain(["member", "casual"]).range(["#1f77b4", "#ff7f0e"]);

// ==========================================
// 1. LINE CHART: Daily rides
// ==========================================
d3.csv("../data/processed/summary/daily.csv").then(function(data) {
    const parseTime = d3.timeParse("%Y-%m-%d");
    data.forEach(d => {
        d.date = parseTime(d.date);
        d.trips = +d.trips;
    });

    const dataByMonth = d3.group(data, d => d3.timeFormat("%Y-%m")(d.date));

    const svg = d3.select("#tv3-line-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3.scaleTime().domain(d3.extent(data, d => d.date)).range([0, width]);
    const y = d3.scaleLinear().domain([0, d3.max(data, d => d.trips) * 1.1]).nice().range([height, 0]);

    svg.append("g").attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(d3.timeMonth.every(1)).tickFormat(d3.timeFormat("%b %Y")));

    svg.append("g").call(d3.axisLeft(y).tickFormat(d3.format("~s")));

    const line = d3.line().x(d => x(d.date)).y(d => y(d.trips));

    dataByMonth.forEach((values, monthKey) => {
        const groupedByType = d3.group(values, d => d.member_type);
        groupedByType.forEach((typeValues, typeName) => {
            typeValues.sort((a, b) => a.date - b.date);
            svg.append("path")
                .datum(typeValues).attr("fill", "none").attr("stroke", colorScale(typeName))
                .attr("stroke-width", 2).attr("d", line);

            svg.selectAll(`.dot-${monthKey}-${typeName}`)
                .data(typeValues).enter().append("circle")
                .attr("cx", d => x(d.date)).attr("cy", d => y(d.trips)).attr("r", 3)
                .attr("fill", colorScale(typeName)).style("opacity", 0)
                .on("mouseover", function(event, d) {
                    d3.select(this).style("opacity", 1).attr("r", 5);
                    tooltip.style("opacity", 1)
                        .html(`Date: <b>${d3.timeFormat("%b %d, %Y")(d.date)}</b><br>Type: ${d.member_type}<br>Trips: <b>${d3.format(",")(d.trips)}</b>`)
                        .style("left", (event.pageX + 15) + "px").style("top", (event.pageY - 28) + "px");
                })
                .on("mouseout", function() {
                    d3.select(this).style("opacity", 0).attr("r", 3);
                    tooltip.style("opacity", 0);
                });
        });
    });
}).catch(error => console.error("Error loading daily data:", error));


// ==========================================
// 2. BAR CHART: Trips by hour
// ==========================================
d3.csv("../data/processed/summary/station_hourly.csv").then(function(rawData) {
    // Tính tổng chuyến đi theo giờ trên toàn bộ các trạm
    const hourlyData = d3.rollups(
        rawData,
        v => d3.sum(v, d => +d.departures), 
        d => d.hour
    ).map(([hour, trips]) => ({ hour: +hour, trips: trips }))
     .sort((a, b) => a.hour - b.hour);

    const svgBar = d3.select("#tv3-bar-chart")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    const xBar = d3.scaleBand().domain(hourlyData.map(d => d.hour)).range([0, width]).padding(0.1);
    const yBar = d3.scaleLinear().domain([0, d3.max(hourlyData, d => d.trips) * 1.1]).nice().range([height, 0]);

    svgBar.append("g").attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(xBar).tickFormat(d => d + "h"));
    svgBar.append("g").call(d3.axisLeft(yBar).tickFormat(d3.format("~s")));

    svgBar.selectAll("rect").data(hourlyData).enter().append("rect")
        .attr("x", d => xBar(d.hour)).attr("y", d => yBar(d.trips))
        .attr("width", xBar.bandwidth()).attr("height", d => height - yBar(d.trips))
        .attr("fill", "#2ca02c").attr("rx", 3)
        .on("mouseover", function(event, d) {
            d3.select(this).attr("fill", "#1f7a1f");
            tooltip.style("opacity", 1)
                .html(`Time: <b>${d.hour}:00</b><br>Total Trips: <b>${d3.format(",")(d.trips)}</b>`)
                .style("left", (event.pageX + 15) + "px").style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            d3.select(this).attr("fill", "#2ca02c");
            tooltip.style("opacity", 0);
        });
}).catch(error => console.error("Error loading hourly data:", error));