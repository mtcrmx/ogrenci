"""Mobile-friendly page images: no browser PDF plugin or forced download."""
from io import BytesIO
from threading import Lock
from flask import abort, make_response, render_template, request, send_file
import pypdfium2 as pdfium

PDF_LOCK=Lock()


def view(path, title, page_url, remaining=None):
    with PDF_LOCK, pdfium.PdfDocument(str(path)) as pdf:
        total=len(pdf)
    page=request.args.get('page',1,type=int)
    if not 1 <= page <= total:abort(404)
    response=make_response(render_template('question_viewer.html',title=title,page=page,total=total,image_url=page_url(page), remaining=remaining))
    response.headers['Cache-Control']='private, no-store'
    return response


def page_image(path, number):
    with PDF_LOCK, pdfium.PdfDocument(str(path)) as pdf:
        if not 1<=number<=len(pdf):abort(404)
        page=pdf[number-1]
        try:
            width,height=page.get_size()
            scale=min(1.8,1800/max(width,height))
            bitmap=page.render(scale=scale)
            try:
                image=bitmap.to_pil();out=BytesIO();image.save(out,format='PNG')
            finally:bitmap.close()
        finally:page.close()
    out.seek(0)
    response=send_file(out,mimetype='image/png')
    response.headers['Cache-Control']='private, no-store'
    return response
