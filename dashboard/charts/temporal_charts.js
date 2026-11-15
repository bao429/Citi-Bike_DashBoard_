// ==========================================
// THÀNH VIÊN 3: TEMPORAL ANALYSIS (FINAL - FIXED CASE SENSITIVITY)
// ==========================================

const margin = { top: 20, right: 100, bottom: 40, left: 60 }; 
const width = 800 - margin.left - margin.right;
const heightLine = 300 - margin.top - margin.bottom;
const heightBar = 250 - margin.top - margin.bottom;

const tooltip = d3.select("#tooltip");
const parseTime = d3.timeParse("%Y-%m-%d");

// Màu sắc và kiểu nét đứt cho 4 tháng
const monthStyles = {
    "Jan": { color: "#d3d3d3", dash: "2,2" },      
    "Apr": { color: "#999999", dash: "6,3" },      
    "Jul": { color: "#555555", dash: "10,4" },     
    "Oct": { color: "#222222", dash: "0" }         
};

const MONTH_ORDER = [
    { code: "2025-01", short: "Jan" },
    { code: "2025-04", short: "Apr" },
    { code: "2025-07", short: "Jul" },
    { code: "2025-10", short: "Oct" }
];

// Trạng thái: Mặc định chọn cả 4 tháng
let selectedMonths = ["2025-01", "2025-04", "2025-07", "2025-10"];

let dailyData = [];
let hourlyData = [];

// Khởi tạo SVG
const svgLine = d3.select("#chart-daily").append("svg")
    .attr("width", width + margin.left + margin.right)
    .attr("height", heightLine + margin.top + margin.bottom)
    .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

const svgHourly = d3.select("#chart-hourly").append("svg")
    .attr("width", (width/2) + margin.left + (margin.right/2))
    .attr("height", heightBar + margin.top + margin.bottom)
    .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

const svgMonthly = d3.select("#chart-monthly").append("svg")
    .attr("width", (width/2) + margin.left + (margin.right/2))
    .attr("height", heightBar + margin.top + margin.bottom)
    .append("g").attr("transform", `translate(${margin.left},${margin.top})`);

// Nhãn nhỏ "Trips" phía trên trục Y
svgLine.append("text")
    .attr("x", -margin.left + 8)
    .attr("y", -6)
    .style("font-size", "11px")
    .style("fill", "#888")
    .text("Trips");

// Load dữ liệu
Promise.all([
    d3.csv("../data/processed/summary/daily.csv"),
    d3.csv("../data/processed/summary/station_hourly.csv")
]).then(function(files) {
    // 1. Xử lý Daily Data
    dailyData = files[0].map(d => {
        const dateObj = parseTime(d.date);
        return {
            date: dateObj,
            day: dateObj.getDate(), 
            monthStr: d3.timeFormat("%Y-%m")(dateObj),
            monthShort: d3.timeFormat("%b")(dateObj),
            member_type: d.member_type.toLowerCase(), // FIX: Đưa về chữ thường
            trips: +d.trips,
            avg_duration: +d.avg_duration_min
        };
    });

    // 2. Xử lý Hourly Data
    hourlyData = files[1].map(d => ({
        monthStr: d.month,
        member_type: d.member_type.toLowerCase(), // FIX: Đưa về chữ thường
        hour: +d.hour,
        departures: +d.departures
    }));

    // Gắn sự kiện Toggle cho các nút Month
    d3.selectAll(".month-btn").on("click", function() {
        const monthVal = this.getAttribute("data-month");
        
        if (selectedMonths.includes(monthVal)) {
            if (selectedMonths.length > 1) { // Giữ lại ít nhất 1 tháng
                selectedMonths = selectedMonths.filter(m => m !== monthVal);
                d3.select(this).classed("active", false);
            }
        } else {
            selectedMonths.push(monthVal);
            d3.select(this).classed("active", true);
        }
        
        updateDashboard();
    });

    // Chạy lần đầu
    updateDashboard();

}).catch(error => console.error("Error loading data:", error));


// ==========================================
// HÀM CẬP NHẬT CHÍNH
// ==========================================
function updateDashboard() {
    const filteredDaily = dailyData.filter(d => selectedMonths.includes(d.monthStr));
    const filteredHourly = hourlyData.filter(d => selectedMonths.includes(d.monthStr));

    updateKPIs(filteredDaily, filteredHourly);
    drawLineChart(filteredDaily);
    drawHourlyChart(filteredHourly);
    drawMonthlyChart(filteredDaily);
}


// ==========================================
// HÀM PHỤ: GỘP TRIPS THEO NGÀY
// ==========================================
function aggregateDailyTotals(data) {
    const map = new Map();
    data.forEach(d => {
        const key = d.date.getTime();
        if (!map.has(key)) {
            map.set(key, {
                date: d.date,
                day: d.day,
                monthStr: d.monthStr,
                monthShort: d.monthShort,
                trips: 0
            });
        }
        map.get(key).trips += d.trips;
    });
    return Array.from(map.values());
}


// ==========================================
// BIỂU ĐỒ 1: DAILY LINE CHART
// ==========================================
function drawLineChart(data) {
    const dailyTotals = aggregateDailyTotals(data);

    const x = d3.scaleLinear().domain([1, 31]).range([0, width]);
    const y = d3.scaleLinear().domain([0, d3.max(dailyTotals, d => d.trips) * 1.1 || 100]).nice().range([heightLine, 0]);

    svgLine.selectAll(".x-axis").data([null]).join("g")
        .attr("class", "x-axis").attr("transform", `translate(0,${heightLine})`)
        .call(d3.axisBottom(x).tickValues([1, 5, 10, 15, 20, 25, 30]).tickFormat(d3.format("d")));

    svgLine.selectAll(".y-axis").data([null]).join("g")
        .attr("class", "y-axis").transition().duration(500).call(d3.axisLeft(y).tickFormat(d3.format("~s")));

    const line = d3.line().x(d => x(d.day)).y(d => y(d.trips));

    const grouped = d3.group(dailyTotals, d => d.monthShort);
    
    const paths = svgLine.selectAll(".line-path").data(Array.from(grouped), d => d[0]);
    
    paths.enter().append("path").attr("class", "line-path")
        .merge(paths)
        .style("pointer-events", "none")
        .transition().duration(500)
        .attr("fill", "none")
        .attr("stroke", d => monthStyles[d[0]].color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", d => monthStyles[d[0]].dash)
        .attr("d", d => line(d[1].slice().sort((a,b) => a.day - b.day)));

    paths.exit().remove();

    // Legend
    const legendData = MONTH_ORDER.filter(m => selectedMonths.includes(m.code)).map(m => m.short);

    const legend = svgLine.selectAll(".legend-item").data(legendData, d => d).join(
        enter => enter.append("g").attr("class", "legend-item")
            .call(g => g.append("line").attr("x1", 0).attr("x2", 15).attr("y1", 5).attr("y2", 5).attr("stroke-width", 2))
            .call(g => g.append("text").attr("x", 20).attr("y", 9).style("font-size", "12px"))
    )
        .attr("transform", (d, i) => `translate(${width + 20}, ${i * 20})`);

    legend.select("line")
        .attr("stroke", d => monthStyles[d].color)
        .attr("stroke-dasharray", d => monthStyles[d].dash);
    legend.select("text").text(d => d);

    setupLineChartTooltip(x, y, grouped);
}

function setupLineChartTooltip(x, y, grouped) {
    const monthGroups = Array.from(grouped);

    const focusLine = svgLine.selectAll(".focus-line").data([null]).join("line")
        .attr("class", "focus-line")
        .attr("stroke", "#999")
        .attr("stroke-dasharray", "4,4")
        .attr("y1", 0)
        .attr("y2", heightLine)
        .style("opacity", 0);

    const focusCircle = svgLine.selectAll(".focus-circle").data([null]).join("circle")
        .attr("class", "focus-circle")
        .attr("r", 4)
        .attr("fill", "#333")
        .style("opacity", 0);

    const overlay = svgLine.selectAll(".overlay").data([null]).join("rect")
        .attr("class", "overlay")
        .attr("width", width)
        .attr("height", heightLine)
        .attr("fill", "none")
        .style("pointer-events", "all");

    overlay.raise();

    overlay
        .on("mousemove", function(event) {
            const [mx, my] = d3.pointer(event, this);
            const day = Math.max(1, Math.min(31, Math.round(x.invert(mx))));

            let candidates = [];
            monthGroups.forEach(([monthShort, rows]) => {
                const point = rows.find(r => r.day === day);
                if (point) candidates.push(point);
            });

            if (candidates.length === 0) {
                focusLine.style("opacity", 0);
                focusCircle.style("opacity", 0);
                tooltip.style("opacity", 0);
                return;
            }

            let nearest = candidates[0];
            let minDist = Infinity;
            candidates.forEach(c => {
                const dist = Math.abs(y(c.trips) - my);
                if (dist < minDist) { minDist = dist; nearest = c; }
            });

            focusLine.attr("x1", x(nearest.day)).attr("x2", x(nearest.day)).style("opacity", 1);
            focusCircle.attr("cx", x(nearest.day)).attr("cy", y(nearest.trips)).style("opacity", 1);

            tooltip.style("opacity", 1)
                .html(`${d3.timeFormat("%b %d (%a)")(nearest.date)}<br>Trips: <b>${d3.format(",")(nearest.trips)}</b>`)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            focusLine.style("opacity", 0);
            focusCircle.style("opacity", 0);
            tooltip.style("opacity", 0);
        });
}


// ==========================================
// BIỂU ĐỒ 2: HOURLY STACKED BAR CHART (FIXED CASE SENSITIVITY)
// ==========================================
function drawHourlyChart(data) {
    const x = d3.scaleBand().domain(d3.range(0, 24)).range([0, (width/2) - 20]).padding(0.2);
    
    let flatData = d3.range(0, 24).map(hour => {
        let memberCount = 0;
        let casualCount = 0;
        
        const hourData = data.filter(d => d.hour === hour);
        
        hourData.forEach(d => {
            if (d.member_type === "member") memberCount += d.departures;
            if (d.member_type === "casual") casualCount += d.departures;
        });

        return { hour: hour, member: memberCount, casual: casualCount };
    });

    const subGroups = ["member", "casual"];
    const stackedData = d3.stack().keys(subGroups)(flatData);

    const maxY = d3.max(flatData, d => d.member + d.casual) || 100;
    const y = d3.scaleLinear().domain([0, maxY * 1.1]).nice().range([heightBar, 0]);

    svgHourly.selectAll(".x-axis").data([null]).join("g")
        .attr("class", "x-axis").attr("transform", `translate(0,${heightBar})`)
        .call(d3.axisBottom(x).tickFormat(d => (d % 4 === 0) ? d + "h" : ""));

    svgHourly.selectAll(".y-axis").data([null]).join("g")
        .attr("class", "y-axis").transition().duration(500).call(d3.axisLeft(y).tickFormat(d3.format("~s")));

    const layer = svgHourly.selectAll(".layer").data(stackedData, d => d.key).join("g").attr("class", "layer");
    
    const rects = layer.selectAll("rect").data(d => d, d => d.data.hour).join("rect")
        .attr("fill", d => d.key === "member" ? "#555" : "#ccc");

    rects
        .on("mouseover", function(event, d) {
            tooltip.style("opacity", 1)
                .html(`${d.data.hour}:00<br>Member: <b>${d3.format(",")(d.data.member)}</b><br>Casual: <b>${d3.format(",")(d.data.casual)}</b>`)
                .style("left", (event.pageX + 15) + "px").style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", () => tooltip.style("opacity", 0));

    rects.transition().duration(500)
        .attr("x", d => x(d.data.hour))
        .attr("y", d => y(d[1]))
        .attr("height", d => y(d[0]) - y(d[1]))
        .attr("width", x.bandwidth());

    // Legend
    const legendData = [{key:"member", label:"Member", color:"#555"}, {key:"casual", label:"Casual", color:"#ccc"}];
    const legend = svgHourly.selectAll(".legend-item").data(legendData, d => d.key).join("g").attr("class", "legend-item")
        .attr("transform", (d, i) => `translate(${i * 80}, -10)`);
    
    legend.selectAll("rect").data(d => [d]).join("rect").attr("width", 12).attr("height", 12).attr("fill", d => d.color);
    legend.selectAll("text").data(d => [d]).join("text").attr("x", 18).attr("y", 10).text(d => d.label).style("font-size", "12px");
}


// ==========================================
// BIỂU ĐỒ 3: MONTHLY GROUPED BAR CHART
// ==========================================
function drawMonthlyChart(data) {
    const activeMonths = MONTH_ORDER.filter(m => selectedMonths.includes(m.code)).map(m => m.short);
    
    const x0 = d3.scaleBand().domain(activeMonths).range([0, (width/2) - 20]).paddingInner(0.2);
    const x1 = d3.scaleBand().domain(["member", "casual"]).range([0, x0.bandwidth()]).padding(0.1);
    
    let flatData = [];
    activeMonths.forEach(monthShort => {
        let memberCount = 0;
        let casualCount = 0;
        
        const monthData = data.filter(d => d.monthShort === monthShort);
        
        monthData.forEach(d => {
            if (d.member_type === "member") memberCount += d.trips;
            if (d.member_type === "casual") casualCount += d.trips;
        });

        flatData.push({ month: monthShort, type: "member", val: memberCount });
        flatData.push({ month: monthShort, type: "casual", val: casualCount });
    });

    const maxVal = d3.max(flatData, d => d.val) || 100;
    const y = d3.scaleLinear().domain([0, maxVal * 1.1]).nice().range([heightBar, 0]);

    svgMonthly.selectAll(".x-axis").data([null]).join("g")
        .attr("class", "x-axis").attr("transform", `translate(0,${heightBar})`)
        .call(d3.axisBottom(x0));

    svgMonthly.selectAll(".y-axis").data([null]).join("g")
        .attr("class", "y-axis").transition().duration(500).call(d3.axisLeft(y).tickFormat(d3.format("~s")));

    const bars = svgMonthly.selectAll(".bar").data(flatData, d => d.month + d.type).join("rect")
        .attr("class", "bar")
        .attr("fill", d => d.type === "member" ? "#555" : "#ccc");

    bars
        .on("mouseover", function(event, d) {
            tooltip.style("opacity", 1)
                .html(`${d.month} - ${d.type === "member" ? "Member" : "Casual"}<br>Trips: <b>${d3.format(",")(d.val)}</b>`)
                .style("left", (event.pageX + 15) + "px").style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", () => tooltip.style("opacity", 0));

    bars.transition().duration(500)
        .attr("x", d => x0(d.month) + x1(d.type))
        .attr("y", d => y(d.val))
        .attr("width", x1.bandwidth())
        .attr("height", d => heightBar - y(d.val));

    // Legend
    const legendData = [{key:"member", label:"Member", color:"#555"}, {key:"casual", label:"Casual", color:"#ccc"}];
    const legend = svgMonthly.selectAll(".legend-item").data(legendData, d => d.key).join("g").attr("class", "legend-item")
        .attr("transform", (d, i) => `translate(${i * 80}, -10)`);
    
    legend.selectAll("rect").data(d => [d]).join("rect").attr("width", 12).attr("height", 12).attr("fill", d => d.color);
    legend.selectAll("text").data(d => [d]).join("text").attr("x", 18).attr("y", 10).text(d => d.label).style("font-size", "12px");
}


// ==========================================
// HÀM CẬP NHẬT KPI
// ==========================================
function updateKPIs(daily, hourly) {
    const total = d3.sum(daily, d => d.trips);
    d3.select("#kpi-total-trips").text(d3.format(",")(total));

    const avgDur = total > 0 ? d3.sum(daily, d => d.avg_duration * d.trips) / total : 0;
    d3.select("#kpi-avg-duration").text(avgDur.toFixed(1) + " min");

    let hourTotals = {};
    hourly.forEach(d => {
        if (!hourTotals[d.hour]) hourTotals[d.hour] = 0;
        hourTotals[d.hour] += d.departures;
    });
    
    let peakHour = "--";
    let maxDepartures = 0;
    for (const [hour, count] of Object.entries(hourTotals)) {
        if (count > maxDepartures) {
            maxDepartures = count;
            peakHour = hour + ":00";
        }
    }
    d3.select("#kpi-peak-hour").text(peakHour);

    let dayTotals = {};
    daily.forEach(d => {
        const dateStr = d.date.toDateString();
        if (!dayTotals[dateStr]) dayTotals[dateStr] = { date: d.date, trips: 0 };
        dayTotals[dateStr].trips += d.trips;
    });
    
    let busiestDay = null;
    let maxTrips = 0;
    for (const key in dayTotals) {
        if (dayTotals[key].trips > maxTrips) {
            maxTrips = dayTotals[key].trips;
            busiestDay = dayTotals[key].date;
        }
    }
    d3.select("#kpi-busiest-day").text(busiestDay ? d3.timeFormat("%b %d")(busiestDay) : "--");
}