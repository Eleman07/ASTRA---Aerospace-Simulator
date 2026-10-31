extends Control
var samples = []
var signal_key = "altitude_m"
var title = "QUOTA · m"

func set_samples(values,key="altitude_m",caption="QUOTA · m"):
    samples=values
    signal_key=key
    title=caption
    queue_redraw()

func _draw():
    var area=Rect2(Vector2(8,25),Vector2(maxf(10,size.x-16),maxf(10,size.y-42)))
    draw_rect(area,Color(.015,.03,.055,.95))
    var font=ThemeDB.fallback_font
    draw_string(font,Vector2(8,16),title,HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color(.55,.76,.97))
    for i in range(5):
        var y=area.position.y+area.size.y*i/4
        draw_line(Vector2(area.position.x,y),Vector2(area.end.x,y),Color(.16,.25,.36),1)
    if samples.size()<2:return
    var values=[]
    var minimum=INF;var maximum=-INF
    for sample in samples:
        var value=sample.get(signal_key)
        if value is float or value is int:
            values.append(float(value));minimum=minf(minimum,float(value));maximum=maxf(maximum,float(value))
    if values.size()<2:return
    var range_value=maxf(maximum-minimum,1.0)
    var points=PackedVector2Array()
    for i in range(values.size()):points.append(Vector2(area.position.x+area.size.x*i/(values.size()-1),area.end.y-(values[i]-minimum)/range_value*area.size.y))
    draw_polyline(points,Color(.24,.7,1),2.0,true)
    draw_string(font,Vector2(area.position.x+4,area.position.y+14),"%.2f"%maximum,HORIZONTAL_ALIGNMENT_LEFT,-1,11,Color(.65,.74,.85))
    draw_string(font,Vector2(area.position.x+4,area.end.y-3),"%.2f"%minimum,HORIZONTAL_ALIGNMENT_LEFT,-1,11,Color(.65,.74,.85))
