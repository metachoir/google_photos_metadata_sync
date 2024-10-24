import os
import json
from datetime import datetime
import piexif
from PIL import Image
import subprocess
import glob
import shutil
import platform
import ctypes
from ctypes import wintypes
import time

def update_creation_time(file_path, timestamp):
    """
    파일의 생성 시간만 업데이트하는 함수
    """
    try:
        # Windows 환경
        if platform.system() == 'Windows':
            # Windows API를 사용하여 생성 시간 변경
            kernel32 = ctypes.WinDLL('kernel32')
            CreateFileW = kernel32.CreateFileW
            SetFileTime = kernel32.SetFileTime
            CloseHandle = kernel32.CloseHandle

            CreateFileW.argtypes = (
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
            )
            CreateFileW.restype = wintypes.HANDLE

            # 파일 핸들 얻기
            handle = CreateFileW(
                file_path, 0x00000100 | 0x00000080,
                0x00000001 | 0x00000002, None, 3, 0x80000000, None
            )

            if handle:
                # FILETIME 구조체로 변환
                timestamp_filetime = int((timestamp + 11644473600) * 10000000)
                ctime = ctypes.c_ulonglong(timestamp_filetime)

                # 생성 시간만 설정 (다른 시간은 NULL 전달)
                SetFileTime(handle, ctypes.byref(ctime), None, None)
                CloseHandle(handle)
        else:
            # Unix 계열 시스템
            # birthtime 지원하는 파일시스템에서만 동작
            os.utime(file_path, (time.time(), os.path.getmtime(file_path)))

        return True
    except Exception as e:
        print(f"파일 생성 시간 업데이트 중 오류 발생: {e}")
        return False

def process_mp4(mp4_file, json_file):
    """
    MP4 파일과 해당 JSON 메타데이터를 처리하는 함수
    """
    try:
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 생성 시간 가져오기
        creation_timestamp = int(metadata['creationTime']['timestamp'])
        
        # 파일 생성 시간 업데이트
        update_creation_time(mp4_file, creation_timestamp)
        
        date_created = datetime.fromtimestamp(creation_timestamp)
        
        print(f"성공: {mp4_file}")
        print(f"  - 파일 생성 시간 변경: {date_created}")
        
        # GPS 정보가 있고 ffmpeg가 설치되어 있다면 GPS 메타데이터 추가
        if 'geoDataExif' in metadata and shutil.which('ffmpeg'):
            try:
                lat = metadata['geoDataExif']['latitude']
                lon = metadata['geoDataExif']['longitude']
                
                # 임시 파일 생성
                temp_output = mp4_file + '.temp.mp4'
                
                # ffmpeg 명령어로 GPS 메타데이터 추가
                cmd = [
                    'ffmpeg', '-i', mp4_file,
                    '-metadata', f'location={lat}/{lon}',
                    '-metadata', f'creation_time={date_created.strftime("%Y-%m-%dT%H:%M:%S")}',
                    '-codec', 'copy',
                    temp_output
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                # 원본 파일 백업
                backup_file = mp4_file + '.backup'
                os.rename(mp4_file, backup_file)
                
                # 임시 파일을 원본 파일명으로 이동
                os.rename(temp_output, mp4_file)
                
                # 백업 파일 삭제
                os.remove(backup_file)
                
                print(f"  - GPS 메타데이터 추가됨: {lat}, {lon}")
                
            except Exception as e:
                print(f"  - GPS 메타데이터 추가 실패: {e}")
                if os.path.exists(temp_output):
                    os.remove(temp_output)
        
        return True
        
    except Exception as e:
        print(f"오류: {mp4_file} 처리 중 문제가 발생했습니다: {e}")
        return False

def process_jpg(jpg_file, json_file, root_dir):
    """
    JPG 파일과 해당 JSON 메타데이터를 처리하는 함수
    """
    try:
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 생성 시간 가져오기
        creation_timestamp = int(metadata['creationTime']['timestamp'])
        # 촬영 시간 가져오기 (EXIF용)
        photo_taken_timestamp = int(metadata['photoTakenTime']['timestamp'])
        
        # 타임스탬프를 datetime으로 변환
        date_taken = datetime.fromtimestamp(photo_taken_timestamp)
        
        # EXIF 데이터 준비
        exif_date = date_taken.strftime("%Y:%m:%d %H:%M:%S")
        
        try:
            # 이미지 열기
            img = Image.open(jpg_file)
            
            try:
                # 기존 EXIF 데이터 가져오기
                exif_dict = piexif.load(img.info.get('exif', b''))
            except Exception as exif_error:
                print(f"  - 경고: 기존 EXIF 데이터를 읽을 수 없습니다. 새로 생성합니다: {exif_error}")
                exif_dict = {'0th': {}, '1st': {}, 'Exif': {}, 'GPS': {}, 'Interop': {}}
            
            if exif_dict is None:
                exif_dict = {'0th': {}, '1st': {}, 'Exif': {}, 'GPS': {}, 'Interop': {}}
            
            # 필요한 딕셔너리 키가 있는지 확인
            for ifd in ['0th', '1st', 'Exif', 'GPS', 'Interop']:
                if ifd not in exif_dict:
                    exif_dict[ifd] = {}
            
            # EXIF 날짜 정보 업데이트
            try:
                exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date
            except Exception as date_error:
                print(f"  - 경고: EXIF 날짜 정보 업데이트 실패: {date_error}")
            
            success = True
            
            # GPS 정보가 있다면 추가
            if 'geoDataExif' in metadata:
                try:
                    lat = metadata['geoDataExif']['latitude']
                    lon = metadata['geoDataExif']['longitude']
                    alt = metadata['geoDataExif']['altitude']
                    
                    # GPS 데이터 변환
                    lat_deg = int(abs(lat))
                    lat_min = int((abs(lat) - lat_deg) * 60)
                    lat_sec = int(((abs(lat) - lat_deg) * 60 - lat_min) * 60 * 100)
                    
                    lon_deg = int(abs(lon))
                    lon_min = int((abs(lon) - lon_deg) * 60)
                    lon_sec = int(((abs(lon) - lon_deg) * 60 - lon_min) * 60 * 100)
                    
                    # GPS 데이터 유효성 검사
                    if all(isinstance(x, (int, float)) for x in [lat_deg, lat_min, lat_sec, lon_deg, lon_min, lon_sec]):
                        exif_dict['GPS'] = {
                            piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
                            piexif.GPSIFD.GPSLatitude: ((lat_deg, 1), (lat_min, 1), (lat_sec, 100)),
                            piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
                            piexif.GPSIFD.GPSLongitude: ((lon_deg, 1), (lon_min, 1), (lon_sec, 100)),
                        }
                        
                        # 고도 정보가 유효한 경우에만 추가
                        if isinstance(alt, (int, float)):
                            exif_dict['GPS'][piexif.GPSIFD.GPSAltitude] = (int(abs(alt) * 100), 100)
                            exif_dict['GPS'][piexif.GPSIFD.GPSAltitudeRef] = 1 if alt < 0 else 0
                    
                except Exception as gps_error:
                    print(f"  - 경고: GPS 데이터 처리 중 오류 발생: {gps_error}")
            
            try:
                # EXIF 데이터를 바이트로 변환
                exif_bytes = piexif.dump(exif_dict)
                
                # 새로운 EXIF 데이터로 이미지 저장
                img.save(jpg_file, 'jpeg', exif=exif_bytes, quality='keep')
                print(f"성공: {jpg_file}")
                print(f"  - EXIF 메타데이터 업데이트 완료")
            except Exception as save_error:
                print(f"  - 경고: EXIF 데이터 저장 중 오류 발생: {save_error}")
                # EXIF 없이 저장 시도
                try:
                    img.save(jpg_file, 'jpeg', quality='keep')
                    print(f"  - EXIF 없이 이미지 저장됨")
                except Exception as final_save_error:
                    print(f"  - 오류: 이미지 저장 실패: {final_save_error}")
                    success = False
            
            # 파일 생성 시간만 업데이트
            if not update_creation_time(jpg_file, creation_timestamp):
                success = False
            else:
                print(f"  - 파일 생성 시간 변경: {datetime.fromtimestamp(creation_timestamp)}")
            
            # 성공적으로 처리된 경우에만 JSON 파일 이동
            if success:
                if move_processed_json(json_file, root_dir):
                    print(f"  - JSON 파일 이동됨: {os.path.basename(json_file)}")
                else:
                    print(f"  - JSON 파일 이동 실패: {os.path.basename(json_file)}")
            
            return success
            
        except Exception as img_error:
            print(f"  - 오류: 이미지 처리 중 문제가 발생했습니다: {img_error}")
            return False
            
    except Exception as e:
        print(f"오류: {jpg_file} 처리 중 문제가 발생했습니다: {e}")
        return False

def move_processed_json(json_path, root_dir):
    """
    처리 완료된 JSON 파일을 processed_json 폴더로 이동하는 함수
    원본 폴더 구조를 유지하면서 이동
    """
    try:
        # processed_json 폴더 경로 생성
        processed_dir = os.path.join(root_dir, 'processed_json')
        
        # 원본 JSON 파일의 상대 경로 구하기
        rel_path = os.path.relpath(json_path, root_dir)
        
        # 새로운 경로 생성
        new_json_path = os.path.join(processed_dir, rel_path)
        
        # 새 경로의 디렉토리 생성
        os.makedirs(os.path.dirname(new_json_path), exist_ok=True)
        
        # JSON 파일 이동
        shutil.move(json_path, new_json_path)
        return True
    except Exception as e:
        print(f"JSON 파일 이동 중 오류 발생: {e}")
        return False

def process_mp4(mp4_file, json_file, root_dir):
    """
    MP4 파일과 해당 JSON 메타데이터를 처리하는 함수
    """
    try:
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 생성 시간 가져오기
        creation_timestamp = int(metadata['creationTime']['timestamp'])
        
        # 파일 생성 시간 업데이트
        update_creation_time(mp4_file, creation_timestamp)
        
        date_created = datetime.fromtimestamp(creation_timestamp)
        
        success = True
        print(f"성공: {mp4_file}")
        print(f"  - 파일 생성 시간 변경: {date_created}")
        
        # GPS 정보가 있고 ffmpeg가 설치되어 있다면 GPS 메타데이터 추가
        if 'geoDataExif' in metadata and shutil.which('ffmpeg'):
            try:
                lat = metadata['geoDataExif']['latitude']
                lon = metadata['geoDataExif']['longitude']
                
                temp_output = mp4_file + '.temp.mp4'
                
                cmd = [
                    'ffmpeg', '-i', mp4_file,
                    '-metadata', f'location={lat}/{lon}',
                    '-metadata', f'creation_time={date_created.strftime("%Y-%m-%dT%H:%M:%S")}',
                    '-codec', 'copy',
                    temp_output
                ]
                
                subprocess.run(cmd, check=True, capture_output=True)
                
                backup_file = mp4_file + '.backup'
                os.rename(mp4_file, backup_file)
                os.rename(temp_output, mp4_file)
                os.remove(backup_file)
                
                print(f"  - GPS 메타데이터 추가됨: {lat}, {lon}")
            except Exception as e:
                print(f"  - GPS 메타데이터 추가 실패: {e}")
                success = False
                if os.path.exists(temp_output):
                    os.remove(temp_output)
        
        # 성공적으로 처리된 경우에만 JSON 파일 이동
        if success:
            if move_processed_json(json_file, root_dir):
                print(f"  - JSON 파일 이동됨: {os.path.basename(json_file)}")
            else:
                print(f"  - JSON 파일 이동 실패: {os.path.basename(json_file)}")
        
        return success
        
    except Exception as e:
        print(f"오류: {mp4_file} 처리 중 문제가 발생했습니다: {e}")
        return False

def process_jpg(jpg_file, json_file, root_dir):
    """
    JPG 파일과 해당 JSON 메타데이터를 처리하는 함수
    """
    try:
        # JSON 파일 읽기
        with open(json_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 생성 시간 가져오기
        creation_timestamp = int(metadata['creationTime']['timestamp'])
        # 촬영 시간 가져오기 (EXIF용)
        photo_taken_timestamp = int(metadata['photoTakenTime']['timestamp'])
        
        # 타임스탬프를 datetime으로 변환
        date_taken = datetime.fromtimestamp(photo_taken_timestamp)
        
        # EXIF 데이터 준비
        exif_date = date_taken.strftime("%Y:%m:%d %H:%M:%S")
        
        # 이미지 열기
        img = Image.open(jpg_file)
        
        # 기존 EXIF 데이터 가져오기
        exif_dict = piexif.load(img.info.get('exif', b''))
        if exif_dict is None:
            exif_dict = {'0th': {}, '1st': {}, 'Exif': {}, 'GPS': {}, 'Interop': {}}
        
        # EXIF 날짜 정보 업데이트
        exif_dict['0th'][piexif.ImageIFD.DateTime] = exif_date
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = exif_date
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = exif_date
        
        success = True
        # GPS 정보가 있다면 추가
        if 'geoDataExif' in metadata:
            try:
                lat = metadata['geoDataExif']['latitude']
                lon = metadata['geoDataExif']['longitude']
                alt = metadata['geoDataExif']['altitude']
                
                # GPS 데이터 변환
                lat_deg = int(abs(lat))
                lat_min = int((abs(lat) - lat_deg) * 60)
                lat_sec = int(((abs(lat) - lat_deg) * 60 - lat_min) * 60 * 100)
                
                lon_deg = int(abs(lon))
                lon_min = int((abs(lon) - lon_deg) * 60)
                lon_sec = int(((abs(lon) - lon_deg) * 60 - lon_min) * 60 * 100)
                
                exif_dict['GPS'] = {
                    piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
                    piexif.GPSIFD.GPSLatitude: ((lat_deg, 1), (lat_min, 1), (lat_sec, 100)),
                    piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
                    piexif.GPSIFD.GPSLongitude: ((lon_deg, 1), (lon_min, 1), (lon_sec, 100)),
                    piexif.GPSIFD.GPSAltitude: (int(alt * 100), 100),
                }
            except Exception as e:
                print(f"GPS 데이터 처리 중 오류 발생: {e}")
                success = False
        
        # EXIF 데이터를 바이트로 변환
        exif_bytes = piexif.dump(exif_dict)
        
        # 새로운 EXIF 데이터로 이미지 저장
        img.save(jpg_file, 'jpeg', exif=exif_bytes)
        
        # 파일 생성 시간만 업데이트
        if not update_creation_time(jpg_file, creation_timestamp):
            success = False
        
        print(f"성공: {jpg_file}")
        print(f"  - EXIF 메타데이터 업데이트 완료")
        print(f"  - 파일 생성 시간 변경: {datetime.fromtimestamp(creation_timestamp)}")
        
        # 성공적으로 처리된 경우에만 JSON 파일 이동
        if success:
            if move_processed_json(json_file, root_dir):
                print(f"  - JSON 파일 이동됨: {os.path.basename(json_file)}")
            else:
                print(f"  - JSON 파일 이동 실패: {os.path.basename(json_file)}")
        
        return success
        
    except Exception as e:
        print(f"오류: {jpg_file} 처리 중 문제가 발생했습니다: {e}")
        return False

def process_directory(directory):
    """
    주어진 디렉토리와 모든 하위 디렉토리의 미디어 파일을 처리하는 함수
    """
    success_count = 0
    error_count = 0
    processed_count = 0
    
    print(f"\n디렉토리 처리 중: {directory}")
    
    # processed_json 폴더 생성
    processed_dir = os.path.join(directory, 'processed_json')
    os.makedirs(processed_dir, exist_ok=True)
    print(f"처리된 JSON 파일 저장 경로: {processed_dir}")
    
    # 모든 jpg와 mp4 파일 찾기
    for root, dirs, files in os.walk(directory):
        # processed_json 폴더 건너뛰기
        if 'processed_json' in root:
            continue
            
        media_files = [f for f in files if f.lower().endswith(('.jpg', '.mp4'))]
        
        if media_files:
            print(f"\n폴더 처리 중: {root}")
            
        for media_file in media_files:
            processed_count += 1
            media_path = os.path.join(root, media_file)
            json_path = media_path + '.json'
            
            # 대응하는 json 파일이 있는지 확인
            if not os.path.exists(json_path):
                print(f"건너뜀: {media_file} - JSON 파일이 없습니다.")
                continue
            
            # 파일 확장자에 따라 적절한 처리 함수 호출
            if media_file.lower().endswith('.jpg'):
                if process_jpg(media_path, json_path, directory):
                    success_count += 1
                else:
                    error_count += 1
            elif media_file.lower().endswith('.mp4'):
                if process_mp4(media_path, json_path, directory):
                    success_count += 1
                else:
                    error_count += 1
    
    return processed_count, success_count, error_count

if __name__ == "__main__":
    # 스크립트가 있는 디렉토리에서 시작
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    print("Google Photos 미디어 메타데이터 동기화 도구")
    print("==========================================")
    print(f"시작 디렉토리: {script_directory}")
    
    # ffmpeg 설치 확인
    if not shutil.which('ffmpeg'):
        print("\n주의: ffmpeg가 설치되어 있지 않습니다.")
        print("MP4 파일의 GPS 메타데이터는 추가되지 않습니다.")
        print("ffmpeg 설치를 추천드립니다.\n")
    
    # 처리 시작
    total_processed, total_success, total_error = process_directory(script_directory)
    
    # 결과 출력
    print("\n처리 완료 요약")
    print("==========================================")
    print(f"총 처리된 미디어 파일: {total_processed}")
    print(f"성공: {total_success}")
    print(f"실패: {total_error}")
    print("==========================================")
