import re
import cv2
import numpy as np
import pytesseract
import csv

def areaFilter(minArea, inputImage):
    # Perform an area filter on the binary blobs:
    componentsNumber, labeledImage, componentStats, componentCentroids = \
    cv2.connectedComponentsWithStats(inputImage, connectivity=4)

    # Get the indices/labels of the remaining components based on the area stat
    # (skip the background component at index 0)
    remainingComponentLabels = [i for i in range(1, componentsNumber) if componentStats[i][4] >= minArea]

    # Filter the labeled pixels based on the remaining labels,
    # assign pixel intensity to 255 (uint8) for the remaining pixels
    filteredImage = np.where(np.isin(labeledImage, remainingComponentLabels) == True, 255, 0).astype('uint8')

    return filteredImage


def get_array_of_rappi_values(inputImagePath):
    MAX_CROP_HEIGHT = 120
    output = []

    inputImage = cv2.imread(inputImagePath)
    grayInput = cv2.cvtColor(inputImage, cv2.COLOR_BGR2GRAY)
    # Set the thresholds
    lowerThresh = 220
    upperThresh = 240
    # Get the lines mask
    mask = cv2.inRange(grayInput, lowerThresh, upperThresh)
    minArea = 50
    mask = areaFilter(minArea, mask)
    
    # Reduce matrix to a n row x 1 columns matrix:
    # reducedImage = cv2.reduce(mask, 1, cv2.REDUCE_MAX)
    # Find the big contours/blobs on the filtered image:
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    # Store the lines here:
    separatingLines = []
    # We need some dimensions of the original image:
    imageHeight = inputImage.shape[0]
    imageWidth = inputImage.shape[1]

    # Look for the outer bounding boxes:
    for _, c in enumerate(contours):
        # Approximate the contour to a polygon:
        contoursPoly = cv2.approxPolyDP(c, 3, True)
        # Convert the polygon to a bounding rectangle:
        boundRect = cv2.boundingRect(contoursPoly)
        # Get the bounding rect's data:
        [x, y, w, h] = boundRect
        # Start point and end point:
        lineCenter = y + (0.5 * h)
        startPoint = (0,int(lineCenter))
        endPoint = (int(imageWidth), int(lineCenter))
        # Store the end point in list:
        separatingLines.append( endPoint )
    # Sort the list based on ascending Y values:
    separatingLines = sorted(separatingLines, key=lambda x: x[1])
    # The past processed vertical coordinate:
    pastY = 0
    # Crop the sections:
    for i in range(len(separatingLines)):
        # Get the current line width and starting y:
        (sectionWidth, sectionHeight) = separatingLines[i]
        # Set the ROI:
        x = 0
        y = pastY
        cropWidth = sectionWidth
        cropHeight = sectionHeight - y
        # Crop the ROI:
        currentCrop = inputImage[y:y + cropHeight, x:x + cropWidth]
        if(cropHeight > MAX_CROP_HEIGHT):
            str = pytesseract.image_to_string(currentCrop, lang='spa')
            output.append(str)
        # Set the next starting vertical coordinate:
        pastY = sectionHeight
    return output

def evaluate_rules(value):
    arr = value.split('\n')
    d = {
        "description": arr[0],
        "year": "",
        "month": "",
        "day": "",
        "value": "",
        "thousands_sep": ""
        }
    regex = [
        r".*?(?P<day>[0-9]{1,2}) ?(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ?(?P<year>20[0-9]{2}).?",
        r"\$(?P<value>[0-9]{1,3}(?P<thousands_sep>[,:\.]){1}[0-9]{3}.?)",
        r".*?(?P<day>[0-9]{1,2}) ?(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) ?(?P<year>20[0-9]{2}).+ \$(?P<value>[0-9]{1,3}(?P<thousands_sep>[,:\.]){1}[0-9]{3}$)",
        #r"(?P<description>[ A-Za-zÀ-ÖØ-öø-ÿ]+) \$(?P<value>[0-9]{1,3}(?P<thousands_sep>[,:\.]){1}[0-9]{3}$)",
        r"(?P<description>.+) \$(?P<value>[0-9]{1,3}(?P<thousands_sep>[,:\.]){1}[0-9]{3}$)",
    ]
    for el in arr:
        for rx in regex:
            m = re.match(rx, el)
            if m is not None:
                d = d | m.groupdict()
    return d

def get_categoria(descripcion):
    lower_descripcion = descripcion.lower()
    if not descripcion: return ""
    if "rappi" in lower_descripcion: return "ALIMENTACION|Domicilios"
    if "netflix" in lower_descripcion: return "ENTRETENIMIENTO|Netflix"

def final_print(d):
    return {
        "tipo": "Gasto",
        "categoria": get_categoria(d["description"]),
        "medio": "RappiCard",
        "tc_pago": "FALSE",
        "fecha": f'{d["year"]}/{d["month"]}/{d["day"]}',
        "descripcion": d["description"],
        "valor": d["value"].replace(d["thousands_sep"], '')
    }
        

def get_actual_values(array_of_values):
    columns = ["tipo","fecha","categoria","medio","descripcion","valor","tc_pago"]
    result = []
    for value in array_of_values:
        print(value)
        temp_dict = evaluate_rules(value)
        d = final_print(temp_dict)
        result.append(d)
    with open('output', 'w', encoding='utf8', newline='') as output_file:
        fc = csv.DictWriter(output_file, fieldnames=columns, delimiter="\t")
        fc.writeheader()
        fc.writerows(result)